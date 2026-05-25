"""file version history

Revision ID: 009
Revises: 008
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _table_exists("file_versions"):
        op.create_table(
            "file_versions",
            sa.Column("id",         sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("file_id",    sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version",    sa.Integer,                                nullable=False),
            sa.Column("content",    sa.Text,                                   nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_file_versions_file_id", "file_versions", ["file_id"])


def downgrade():
    op.drop_table("file_versions")
