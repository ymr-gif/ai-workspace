"""messages tsvector generated column + GIN index for full-text conversation search

Revision ID: 020
Revises: 019
Create Date: 2026-05-27
"""
from alembic import op

revision      = "020"
down_revision = "019"
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        ALTER TABLE messages
        ADD COLUMN IF NOT EXISTS content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_gin ON messages USING gin(content_tsv)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_messages_gin")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS content_tsv")
