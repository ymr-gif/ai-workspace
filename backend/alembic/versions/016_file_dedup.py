"""add sha256_hash to files for deduplication

Revision ID: 016
Revises: 015
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("files", sa.Column("sha256_hash", sa.String(64), nullable=True))
    op.create_index("ix_files_user_sha256", "files", ["user_id", "sha256_hash"])


def downgrade():
    op.drop_index("ix_files_user_sha256", table_name="files")
    op.drop_column("files", "sha256_hash")
