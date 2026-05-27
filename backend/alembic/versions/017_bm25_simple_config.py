"""bm25 tsvector: switch from 'english' to 'simple' for multilingual support

Revision ID: 017
Revises: 016
Create Date: 2026-05-27
"""
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    # file_chunks
    op.execute("DROP INDEX IF EXISTS ix_file_chunks_gin")
    op.execute("ALTER TABLE file_chunks DROP COLUMN IF EXISTS content_tsv")
    op.execute("""
        ALTER TABLE file_chunks
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED
    """)
    op.execute("CREATE INDEX ix_file_chunks_gin ON file_chunks USING gin(content_tsv)")

    # message_embeddings
    op.execute("DROP INDEX IF EXISTS ix_message_embeddings_gin")
    op.execute("ALTER TABLE message_embeddings DROP COLUMN IF EXISTS content_tsv")
    op.execute("""
        ALTER TABLE message_embeddings
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content_snippet, ''))) STORED
    """)
    op.execute("CREATE INDEX ix_message_embeddings_gin ON message_embeddings USING gin(content_tsv)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_file_chunks_gin")
    op.execute("ALTER TABLE file_chunks DROP COLUMN IF EXISTS content_tsv")
    op.execute("""
        ALTER TABLE file_chunks
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED
    """)
    op.execute("CREATE INDEX ix_file_chunks_gin ON file_chunks USING gin(content_tsv)")

    op.execute("DROP INDEX IF EXISTS ix_message_embeddings_gin")
    op.execute("ALTER TABLE message_embeddings DROP COLUMN IF EXISTS content_tsv")
    op.execute("""
        ALTER TABLE message_embeddings
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(content_snippet, ''))) STORED
    """)
    op.execute("CREATE INDEX ix_message_embeddings_gin ON message_embeddings USING gin(content_tsv)")
