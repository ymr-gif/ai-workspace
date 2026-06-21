"""add media_type and ocr_text to files (Q2 #19 image OCR)

Revision ID: 045
Revises: 044
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision      = "045"
down_revision = "044"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column("files", sa.Column("media_type", sa.String(16), server_default="document", nullable=False))
    op.add_column("files", sa.Column("ocr_text", sa.Text, nullable=True))


def downgrade():
    op.drop_column("files", "ocr_text")
    op.drop_column("files", "media_type")
