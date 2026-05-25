"""add cost_limit_usd to users

Revision ID: 012
Revises: 011
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("cost_limit_usd", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("users", "cost_limit_usd")
