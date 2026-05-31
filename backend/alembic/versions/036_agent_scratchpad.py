"""add agent_scratchpad to UserMemory

Revision ID: 036
Revises: 035
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = "036"
down_revision = "035"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        "user_memory",
        sa.Column("agent_scratchpad", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("user_memory", "agent_scratchpad")
