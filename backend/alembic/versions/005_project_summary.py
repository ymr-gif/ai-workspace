"""add project_summary to user_memory

Revision ID: 005
Revises: 004
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision      = "005"
down_revision = "004"
branch_labels = None
depends_on    = None


def _has_column(table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(op.get_bind()).get_columns(table)]


def upgrade():
    if not _has_column("user_memory", "project_summary"):
        op.add_column("user_memory", sa.Column("project_summary", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("user_memory", "project_summary")
