import argparse
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db.session import SessionLocal
from app.models.raw_record import RawRecord

SCRUBBED_TEXT = "[removed after masking]"


def run_retention(days: int | None = None):
    """
    Replace raw post text with a placeholder once it has been masked and is
    older than the retention window. Keeps source_id (so re-ingesting the same
    post is still recognized as a duplicate) and source_created_at (so the
    post still counts toward the right day). Only masked_records keeps text.
    """
    days = settings.raw_retention_days if days is None else days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    db = SessionLocal()
    try:
        scrubbed = (
            db.query(RawRecord)
            .filter(RawRecord.is_processed == "masked", RawRecord.ingested_at < cutoff)
            .update(
                {"raw_text": SCRUBBED_TEXT, "is_processed": "scrubbed"},
                synchronize_session=False,
            )
        )
        db.commit()
        print(f"Retention: removed raw text from {scrubbed} posts older than {days} days")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None,
                        help="override the retention window (0 = scrub everything masked)")
    run_retention(parser.parse_args().days)