"""030 add chunk quality columns to files table

Revision ID: 030
Revises: 029
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("files", sa.Column("chunk_total",      sa.Integer(), nullable=True))
    op.add_column("files", sa.Column("chunk_embedded",   sa.Integer(), nullable=True))
    op.add_column("files", sa.Column("embed_fail_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("files", "embed_fail_count")
    op.drop_column("files", "chunk_embedded")
    op.drop_column("files", "chunk_total")
