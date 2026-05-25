"""add token usage columns to messages

Revision ID: 011
Revises: 010
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("prompt_tokens",     sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("completion_tokens", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("total_tokens",      sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("cost_usd",          sa.Float(),   nullable=True))


def downgrade():
    op.drop_column("messages", "cost_usd")
    op.drop_column("messages", "total_tokens")
    op.drop_column("messages", "completion_tokens")
    op.drop_column("messages", "prompt_tokens")
