"""add user_memory table

Revision ID: 002
Revises: 001
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision    = "002"
down_revision = "001"
branch_labels = None
depends_on    = None


def upgrade():
    if not inspect(op.get_bind()).has_table("user_memory"):
        op.create_table(
            "user_memory",
            sa.Column("user_id",    sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("content",    sa.Text(),    nullable=False, server_default=""),
            sa.Column("version",    sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade():
    op.drop_table("user_memory")
