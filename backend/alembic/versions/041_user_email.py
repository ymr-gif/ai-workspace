"""add email column to users

Revision ID: 041
Revises: 040
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision      = "041"
down_revision = "040"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("email", sa.String(256), nullable=True, unique=True, index=True),
    )


def downgrade():
    op.drop_index("ix_users_email")
    op.drop_column("users", "email")
