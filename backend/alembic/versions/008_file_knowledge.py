"""file knowledge base — vector chunks + conversation_files

Revision ID: 008
Revises: 007
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision      = "008"
down_revision = "007"
branch_labels = None
depends_on    = None


def _has_column(table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(op.get_bind()).get_columns(table)]


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade():
    # replace ARRAY embedding with vector(1024) on file_chunks
    op.execute("ALTER TABLE file_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE file_chunks ADD COLUMN IF NOT EXISTS embedding vector(1024)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_file_chunks_hnsw "
        "ON file_chunks USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL"
    )

    # conversation_files junction table
    if not _table_exists("conversation_files"):
        op.create_table(
            "conversation_files",
            sa.Column("conversation_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("file_id",         sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("attached_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["file_id"],         ["files.id"],         ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("conversation_id", "file_id"),
        )
        op.create_index("ix_conversation_files_conv", "conversation_files", ["conversation_id"])
        op.create_index("ix_conversation_files_file", "conversation_files", ["file_id"])


def downgrade():
    op.drop_table("conversation_files")
    op.execute("ALTER TABLE file_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE file_chunks ADD COLUMN IF NOT EXISTS embedding float8[]")
