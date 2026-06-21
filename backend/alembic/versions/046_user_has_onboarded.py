"""add User.has_onboarded column (Phase 3b onboarding)

Revision ID: 046
Revises: 045
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision      = "046"
down_revision = "045"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column("users", sa.Column("has_onboarded", sa.Boolean, server_default=sa.text("false"), nullable=False))


def downgrade():
    op.drop_column("users", "has_onboarded")
