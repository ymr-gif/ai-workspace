"""add message_embeddings table with pgvector HNSW index

Revision ID: 004
Revises: 003
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from pgvector.sqlalchemy import Vector

revision      = "004"
down_revision = "003"
branch_labels = None
depends_on    = None

_DIM = 1024


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "message_embeddings",
        sa.Column("id",              pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id",      pg.UUID(as_uuid=True), sa.ForeignKey("messages.id",      ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_snippet", sa.Text(),  nullable=False),
        sa.Column("embedding",       Vector(_DIM), nullable=False),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_message_embeddings_conversation_id", "message_embeddings", ["conversation_id"])
    op.create_index("ix_message_embeddings_message_id",      "message_embeddings", ["message_id"])
    op.execute("CREATE INDEX ON message_embeddings USING hnsw (embedding vector_cosine_ops)")


def downgrade():
    op.drop_table("message_embeddings")
