"""create topic_daily_stats table

Revision ID: 6bc6b3c902a2
Revises: f2f09c892be6
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6bc6b3c902a2"
down_revision: Union[str, Sequence[str], None] = "f2f09c892be6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "topic_daily_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        # create_type=False: the "focusarea" enum already exists (created for
        # topic_assignments). Without this, Postgres rejects a second CREATE TYPE.
        sa.Column(
            "focus_area",
            postgresql.ENUM(
                "ASSISTIVE_TECH_DIGITAL_ACCESS",
                "ORIENTATION_MOBILITY",
                "COMMUNITY_IDENTITY_SOCIAL",
                "HEALTHCARE_VISION_DIAGNOSIS",
                "DAILY_LIVING_UNCATEGORIZED",
                name="focusarea",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("post_count", sa.Integer(), nullable=False),
        sa.Column("avg_friction", sa.Float(), nullable=True),
        sa.Column("avg_polarity", sa.Float(), nullable=True),
        sa.Column("volume_velocity", sa.Float(), nullable=True),
        sa.Column("engagement_weight", sa.Float(), nullable=True),
        sa.Column("friction_intensity", sa.Float(), nullable=True),
        sa.Column("urgency_score", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stat_date", "focus_area", name="uq_topic_daily_date_area"),
    )


def downgrade() -> None:
    # Only drop the table. Do NOT drop the "focusarea" type here:
    # topic_assignments still depends on it.
    op.drop_table("topic_daily_stats")