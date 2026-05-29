"""memory_conflict expires_at column

Revision ID: 031
Revises: 030
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memory_conflicts", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("memory_conflicts", "expires_at")
