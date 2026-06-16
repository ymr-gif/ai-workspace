"""add render_meta to messages (grounding badge persistence)

Revision ID: 044
Revises: 043
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision      = "044"
down_revision = "043"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column("messages", sa.Column("render_meta", JSONB, nullable=True))


def downgrade():
    op.drop_column("messages", "render_meta")
