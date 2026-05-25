"""hybrid search — tsvector generated columns + GIN indexes

Revision ID: 013
Revises: 012
Create Date: 2026-05-26
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        ALTER TABLE file_chunks
        ADD COLUMN IF NOT EXISTS content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_file_chunks_gin "
        "ON file_chunks USING gin(content_tsv)"
    )

    op.execute("""
        ALTER TABLE message_embeddings
        ADD COLUMN IF NOT EXISTS content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(content_snippet, ''))) STORED
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_message_embeddings_gin "
        "ON message_embeddings USING gin(content_tsv)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_message_embeddings_gin")
    op.execute("ALTER TABLE message_embeddings DROP COLUMN IF EXISTS content_tsv")
    op.execute("DROP INDEX IF EXISTS ix_file_chunks_gin")
    op.execute("ALTER TABLE file_chunks DROP COLUMN IF EXISTS content_tsv")
