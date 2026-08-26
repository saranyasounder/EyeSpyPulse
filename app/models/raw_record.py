import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.db.session import Base


class SourceType(str, enum.Enum):
    REDDIT = "reddit"
    GOOGLE_SEARCH_CONSOLE = "google_search_console"


class RawRecord(Base):
    __tablename__ = "raw_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Where this record came from
    source = Column(Enum(SourceType), nullable=False)

    # The original source's own ID (e.g. Reddit post ID), so we
    # never ingest the same item twice
    source_id = Column(String, nullable=False, unique=True)

    # The actual text content — unmasked, as pulled from the source
    raw_text = Column(Text, nullable=False)

    # When the content was originally created (posted/searched),
    # not when we ingested it — matters for time-series trends
    source_created_at = Column(DateTime(timezone=True), nullable=True)

    # When our pipeline pulled it in
    ingested_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Has this row been through the PII masker yet?
    is_processed = Column(String, default="pending", nullable=False)

    def __repr__(self):
        return f"<RawRecord source={self.source} source_id={self.source_id}>"