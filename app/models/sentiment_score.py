import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class SentimentScore(Base):
    __tablename__ = "sentiment_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    masked_record_id = Column(
        UUID(as_uuid=True), ForeignKey("masked_records.id"), nullable=False, unique=True
    )

    # Standard polarity: -1.0 (very negative) to +1.0 (very positive)
    polarity = Column(Float, nullable=False)

    # Your custom metric: 0.0 (no friction) to 1.0 (severe systemic barrier).
    # Distinct from polarity — a post can be negative in tone but low-friction
    # (venting about a minor annoyance) or neutral in tone but high-friction
    # (matter-of-factly describing being unable to access something essential).
    friction_index = Column(Float, nullable=False)

    scored_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<SentimentScore polarity={self.polarity} friction={self.friction_index}>"