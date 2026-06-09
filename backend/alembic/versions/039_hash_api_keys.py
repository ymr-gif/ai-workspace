"""invalidate plaintext api keys (now stored as SHA-256 hashes)

Revision ID: 039
Revises: 038
Create Date: 2026-06-09
"""
from alembic import op

revision      = "039"
down_revision = "038"
branch_labels = None
depends_on    = None


def upgrade():
    # Existing keys are plaintext — they can't be migrated without the original value.
    # NULL them out so users regenerate; new keys will be stored as SHA-256 hex.
    op.execute("UPDATE users SET api_key = NULL WHERE api_key IS NOT NULL")


def downgrade():
    pass
