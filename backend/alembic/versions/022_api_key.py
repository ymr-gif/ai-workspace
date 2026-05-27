"""add api_key to users

Revision ID: 022
Revises: 021
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision      = "022"
down_revision = "021"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column("users", sa.Column("api_key", sa.String(64), nullable=True))
    op.create_index("ix_users_api_key", "users", ["api_key"], unique=True)


def downgrade():
    op.drop_index("ix_users_api_key", table_name="users")
    op.drop_column("users", "api_key")
