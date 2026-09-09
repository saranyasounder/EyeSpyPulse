import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class MaskedRecord(Base):
    __tablename__ = "masked_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Link back to the raw record this was derived from
    raw_record_id = Column(
        UUID(as_uuid=True), ForeignKey("raw_records.id"), nullable=False, unique=True
    )

    # The sanitized text — safe for NLP, dashboards, anyone to see
    masked_text = Column(Text, nullable=False)

    # Which entity types were found/redacted (e.g. ["PERSON", "LOCATION"])
    # Useful for auditing masker performance without storing what was found
    entity_types_found = Column(Text, nullable=True)

    masked_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<MaskedRecord raw_record_id={self.raw_record_id}>"