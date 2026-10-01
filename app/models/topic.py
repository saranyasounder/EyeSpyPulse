import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Text, DateTime, ForeignKey, Enum, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.db.session import Base


class FocusArea(str, enum.Enum):
    ASSISTIVE_TECH_DIGITAL_ACCESS = "assistive_tech_digital_access"
    ORIENTATION_MOBILITY = "orientation_mobility"
    COMMUNITY_IDENTITY_SOCIAL = "community_identity_social"
    HEALTHCARE_VISION_DIAGNOSIS = "healthcare_vision_diagnosis"
    DAILY_LIVING_UNCATEGORIZED = "daily_living_uncategorized"


class TopicAssignment(Base):
    """
    One row per masked_record: which fixed focus area it belongs to,
    and which sub-cluster within that area (if any).
    """
    __tablename__ = "topic_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    masked_record_id = Column(
        UUID(as_uuid=True), ForeignKey("masked_records.id"), nullable=False, unique=True
    )

    focus_area = Column(Enum(FocusArea), nullable=False)

    # How confident the classifier was in this focus_area assignment (0-1)
    focus_area_similarity = Column(Float, nullable=False)

    # Sub-cluster ID within the focus area, from HDBSCAN.
    # -1 or NULL means "noise" / no clear sub-cluster (HDBSCAN's own convention)
    sub_cluster_id = Column(Integer, nullable=True)

    # Store the embedding so we don't have to regenerate it for re-clustering
    embedding = Column(ARRAY(Float), nullable=False)

    assigned_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<TopicAssignment focus_area={self.focus_area} sub_cluster={self.sub_cluster_id}>"