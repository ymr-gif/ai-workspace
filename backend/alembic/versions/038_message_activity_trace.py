"""add activity_trace to messages

Revision ID: 038
Revises: 037
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision      = "038"
down_revision = "037"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        "messages",
        sa.Column("activity_trace", JSONB, nullable=True),
    )


def downgrade():
    op.drop_column("messages", "activity_trace")
