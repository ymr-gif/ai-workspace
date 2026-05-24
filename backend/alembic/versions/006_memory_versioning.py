"""add memory_enabled to conversations and user_memory_versions table

Revision ID: 006
Revises: 005
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision      = "006"
down_revision = "005"
branch_labels = None
depends_on    = None


def _has_column(table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(op.get_bind()).get_columns(table)]


def _table_exists(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def upgrade():
    if not _has_column("conversations", "memory_enabled"):
        op.add_column(
            "conversations",
            sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default="true"),
        )

    if not _table_exists("user_memory_versions"):
        op.create_table(
            "user_memory_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("project_summary", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_user_memory_versions_user_id",
            "user_memory_versions",
            ["user_id"],
        )


def downgrade():
    op.drop_index("ix_user_memory_versions_user_id", table_name="user_memory_versions")
    op.drop_table("user_memory_versions")
    op.drop_column("conversations", "memory_enabled")
