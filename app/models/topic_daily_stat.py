import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, UUID

from app.db.session import Base
from app.models.topic import FocusArea


class TopicDailyStat(Base):
    """
    One row per focus area per day: the aggregated numbers behind the
    dashboard, plus the components of the urgency score so the score is
    explainable ("why is this topic urgent today?") and not just a number.
    """
    __tablename__ = "topic_daily_stats"
    __table_args__ = (
        # Re-running the daily job updates a day's row instead of duplicating it
        UniqueConstraint("stat_date", "focus_area", name="uq_topic_daily_date_area"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    stat_date = Column(Date, nullable=False)

    # create_type=False: the "focusarea" Postgres enum already exists (created
    # for topic_assignments). Without this, the migration tries to create the
    # type a second time and fails with "type already exists".
    focus_area = Column(
        PGEnum(FocusArea, name="focusarea", create_type=False), nullable=False
    )

    post_count = Column(Integer, nullable=False)
    avg_friction = Column(Float, nullable=True)
    avg_polarity = Column(Float, nullable=True)

    # Components of the Topic Urgency Score, stored separately for transparency
    volume_velocity = Column(Float, nullable=True)
    engagement_weight = Column(Float, nullable=True)  # NULL until we have engagement data
    friction_intensity = Column(Float, nullable=True)

    urgency_score = Column(Float, nullable=True)

    computed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<TopicDailyStat {self.stat_date} {self.focus_area} urgency={self.urgency_score}>"