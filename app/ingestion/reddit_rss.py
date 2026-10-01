import re
import time
from datetime import datetime, timezone

import feedparser
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db.session import SessionLocal
from app.models.raw_record import RawRecord, SourceType

# Add feeds here. Rules:
#  - Use "/new/" feeds only. Post IDs include the feed path, so mixing
#    /new/ with /hot/ or /top/ would store the same post twice.
#  - Open each URL in a browser first and confirm it shows XML.
#  - "?limit=100" asks for up to 100 posts instead of the default 25, so a busy
#    day doesn't push posts out of the feed before the daily pull. If Reddit
#    rejects it, remove it.
FEED_URLS = [
    "https://www.reddit.com/r/Blind/new/.rss?limit=50",
    "https://www.reddit.com/r/BlindAndFine/new/.rss?limit=50",
    "https://www.reddit.com/r/askblindpeople/new/.rss?limit=50"

]

PAUSE_BETWEEN_FEEDS_SECONDS = 5  # be polite, avoids 429 rate limits
MAX_RETRIES = 3


def feed_label(url: str) -> str:
    match = re.search(r"/r/([^/]+)/", url)
    return f"r/{match.group(1)}" if match else url


def fetch_feed(url: str):
    """Fetch one feed, backing off on 429. Returns [] if it can't be fetched."""
    for attempt in range(1, MAX_RETRIES + 1):
        parsed = feedparser.parse(
            url,
            agent=settings.reddit_user_agent or "es-pulse/0.1",
        )
        status = parsed.get("status")

        if status == 429:
            wait_seconds = 30 * attempt
            print(f"{feed_label(url)}: rate limited (429). Retrying in {wait_seconds}s "
                  f"(attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait_seconds)
            continue

        if status and status >= 400:
            print(f"{feed_label(url)}: unexpected status {status}")
            return []

        return parsed.entries

    print(f"{feed_label(url)}: giving up after {MAX_RETRIES} retries.")
    return []


def entry_to_raw_record(entry) -> RawRecord:
    # entry.id is unique per post per feed path. Keep this exactly as it was so
    # posts already stored are still recognized as duplicates.
    source_id = entry.get("id") or entry.get("link")

    title = entry.get("title", "")
    summary = entry.get("summary", "")
    raw_text = f"{title}\n\n{summary}"

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
    total_new = 0

    try:
        for index, url in enumerate(FEED_URLS):
            if index > 0:
                time.sleep(PAUSE_BETWEEN_FEEDS_SECONDS)

            label = feed_label(url)
            try:
                entries = fetch_feed(url)
            except Exception as exc:  # one bad feed must not stop the others
                print(f"{label}: skipped ({exc})")
                continue

            records = [entry_to_raw_record(e) for e in entries]
            records = [r for r in records if r.source_id]

            ids = [r.source_id for r in records]
            existing = set()
            if ids:
                existing = {
                    sid for (sid,) in
                    db.query(RawRecord.source_id).filter(RawRecord.source_id.in_(ids)).all()
                }

            inserted = 0
            for record in records:
                if record.source_id in existing:
                    continue
                db.add(record)
                try:
                    db.commit()
                    inserted += 1
                    existing.add(record.source_id)
                except IntegrityError:
                    db.rollback()

            total_new += inserted
            print(f"{label}: {len(records)} fetched, {inserted} new, "
                  f"{len(records) - inserted} already stored")
    finally:
        db.close()

    print(f"Ingestion complete: {total_new} new posts across {len(FEED_URLS)} feed(s)")


if __name__ == "__main__":
    run_ingestion()