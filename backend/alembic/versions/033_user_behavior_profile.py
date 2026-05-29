"""user_behavior_profiles table

Revision ID: 033
Revises: 032
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = "033"
down_revision = "032"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "user_behavior_profiles",
        sa.Column("user_id",    sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("profile",    postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("user_behavior_profiles")
