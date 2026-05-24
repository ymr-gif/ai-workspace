"""add history_summary to conversations and last_summarized_at to user_memory

Revision ID: 003
Revises: 002
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision      = "003"
down_revision = "002"
branch_labels = None
depends_on    = None


def _has_column(table: str, column: str) -> bool:
    cols = [c["name"] for c in inspect(op.get_bind()).get_columns(table)]
    return column in cols


def upgrade():
    if not _has_column("conversations", "history_summary"):
        op.add_column("conversations", sa.Column("history_summary", sa.Text(), nullable=True))

    if not _has_column("user_memory", "last_summarized_at"):
        op.add_column("user_memory", sa.Column("last_summarized_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("conversations", "history_summary")
    op.drop_column("user_memory",   "last_summarized_at")
