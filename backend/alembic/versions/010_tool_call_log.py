"""tool call audit log

Revision ID: 010
Revises: 009
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _table_exists("tool_call_logs"):
        op.create_table(
            "tool_call_logs",
            sa.Column("id",              UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id",         sa.Integer,         nullable=False),
            sa.Column("conversation_id", UUID(as_uuid=True), nullable=True),
            sa.Column("tool_name",       sa.String(64),      nullable=False),
            sa.Column("args",            JSONB,              nullable=True),
            sa.Column("result_preview",  sa.Text,            nullable=True),
            sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"],         ["users.id"],         ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_tool_call_logs_user_id",         "tool_call_logs", ["user_id"])
        op.create_index("ix_tool_call_logs_conversation_id", "tool_call_logs", ["conversation_id"])
        op.create_index("ix_tool_call_logs_created_at",      "tool_call_logs", ["created_at"])


def downgrade():
    op.drop_table("tool_call_logs")
