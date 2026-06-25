"""add conversations and messages tables

Revision ID: 001
Revises: 000
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import inspect


revision = "001"
down_revision = "000"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _table_exists("conversations"):
        op.create_table(
            "conversations",
            sa.Column("id",         UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id",    sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title",      sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    if not _table_exists("messages"):
        op.create_table(
            "messages",
            sa.Column("id",              UUID(as_uuid=True), primary_key=True),
            sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role",            sa.String(20),  nullable=False),
            sa.Column("content",         sa.Text(),      nullable=False),
            sa.Column("model",           sa.String(100), nullable=True),
            sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade():
    op.drop_table("messages")
    op.drop_table("conversations")
