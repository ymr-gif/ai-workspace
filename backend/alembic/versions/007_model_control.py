"""add system_prompt and locked_model to conversations

Revision ID: 007
Revises: 006
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision      = "007"
down_revision = "006"
branch_labels = None
depends_on    = None


def _has_column(table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(op.get_bind()).get_columns(table)]


def upgrade():
    if not _has_column("conversations", "system_prompt"):
        op.add_column("conversations", sa.Column("system_prompt", sa.Text(), nullable=True))
    if not _has_column("conversations", "locked_model"):
        op.add_column("conversations", sa.Column("locked_model", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("conversations", "locked_model")
    op.drop_column("conversations", "system_prompt")
