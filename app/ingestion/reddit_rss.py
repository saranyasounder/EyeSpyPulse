import time
from datetime import datetime, timezone

import feedparser
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.raw_record import RawRecord, SourceType
from app.config import settings

FEED_URLS = [
    "https://www.reddit.com/r/Blind/new/.rss",
]


def fetch_feed(url: str, max_retries: int = 3):
    """Parse a single RSS feed and return its entries, with backoff on 429."""
    for attempt in range(1, max_retries + 1):
        parsed = feedparser.parse(
            url,
            agent=settings.reddit_user_agent or "es-pulse/0.1 (by u/YourUsername)",
        )
        status = parsed.get("status")

        if status == 429:
            wait_seconds = 30 * attempt  # 30s, 60s, 90s
            print(
                f"Rate limited (429) on {url}. Retrying in {wait_seconds}s "
                f"(attempt {attempt}/{max_retries})..."
            )
            time.sleep(wait_seconds)
            continue

        if parsed.bozo and status != 200:
            print(f"Warning: unexpected status {status} for {url}")
            print(f"  reason: {parsed.get('bozo_exception')}")

        return parsed.entries

    print(f"Giving up on {url} after {max_retries} retries.")
    return []


def entry_to_raw_record(entry) -> RawRecord:
    """Map one RSS entry to a RawRecord row."""
    # entry.id is Reddit's stable post URL — good unique source_id
    source_id = entry.get("id") or entry.get("link")

    # entry.summary contains an HTML snippet in Reddit's RSS —
    # combine title + summary as the raw text for now
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    raw_text = f"{title}\n\n{summary}"

    # RSS gives a parsed time struct; convert to a real datetime
    published = entry.get("published_parsed")
    source_created_at = (
        datetime(*published[:6], tzinfo=timezone.utc) if published else None
    )

    return RawRecord(
        source=SourceType.REDDIT,
        source_id=source_id,
        raw_text=raw_text,
        source_created_at=source_created_at,
    )


def run_ingestion():
    db = SessionLocal()
    inserted, skipped = 0, 0

    try:
        for url in FEED_URLS:
            entries = fetch_feed(url)
            print(f"Fetched {len(entries)} entries from {url}")

            for entry in entries:
                record = entry_to_raw_record(entry)

                try:
                    db.add(record)
                    db.commit()
                    inserted += 1
                except IntegrityError as e:
                    db.rollback()
                    # e.orig has the real Postgres error text —
                    # this tells us whether it's truly a duplicate
                    # key violation or something else entirely
                    print(f"IntegrityError on {record.source_id}: {e.orig}")
                    skipped += 1
                except Exception as e:
                    db.rollback()
                    print(
                        f"UNEXPECTED error on {record.source_id}: "
                        f"{type(e).__name__}: {e}"
                    )
                    # don't re-raise here — one bad row shouldn't kill
                    # the whole batch; just skip it and move on
                    skipped += 1
    finally:
        db.close()

    print(
        f"Ingestion complete: {inserted} inserted, {skipped} duplicates/errors skipped"
    )


if __name__ == "__main__":
    run_ingestion()
