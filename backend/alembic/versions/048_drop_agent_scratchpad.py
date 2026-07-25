"""drop dead UserMemory.agent_scratchpad column (canvas removed 2026-06-09)

The canvas feature was removed 2026-06-09; this JSONB column (added by 036) has had
no reader or writer since. Dropping it as part of the full canvas-artifact cleanup.

Revision ID: 048
Revises: 047
Create Date: 2026-07-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = "048"
down_revision = "047"
branch_labels = None
depends_on    = None


def upgrade():
    op.drop_column("user_memory", "agent_scratchpad")


def downgrade():
    op.add_column(
        "user_memory",
        sa.Column("agent_scratchpad", postgresql.JSONB(), nullable=True),
    )
