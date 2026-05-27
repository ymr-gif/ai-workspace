"""025 cost window days

Revision ID: 025
Revises: 024
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op

revision     = "025"
down_revision = "024"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column("users", sa.Column("cost_window_days", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("users", "cost_window_days")
