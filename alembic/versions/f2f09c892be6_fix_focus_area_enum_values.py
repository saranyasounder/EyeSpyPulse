"""fix focus area enum values

Revision ID: f2f09c892be6
Revises: e2a08e618009
Create Date: 2026-09-09 18:41:43.859989

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2f09c892be6'
down_revision: Union[str, Sequence[str], None] = 'e2a08e618009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


"""fix focus area enum values"""


def upgrade():
    op.execute("ALTER TYPE focusarea RENAME TO focusarea_old")

    op.execute("""
        CREATE TYPE focusarea AS ENUM (
            'ASSISTIVE_TECH_DIGITAL_ACCESS',
            'ORIENTATION_MOBILITY',
            'COMMUNITY_IDENTITY_SOCIAL',
            'HEALTHCARE_VISION_DIAGNOSIS',
            'DAILY_LIVING_UNCATEGORIZED'
        )
    """)

    op.execute("""
        ALTER TABLE topic_assignments
        ALTER COLUMN focus_area TYPE focusarea
        USING focus_area::text::focusarea
    """)

    op.execute("DROP TYPE focusarea_old")


def downgrade():
    pass
