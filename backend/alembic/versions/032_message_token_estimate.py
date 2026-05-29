"""add token_estimate flag and backfill NULL-token assistant messages

Revision ID: 032
Revises: 031
Create Date: 2026-05-29
"""
import sqlalchemy as sa
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("token_estimate", sa.Boolean(), nullable=True))

    op.execute("""
        UPDATE messages
        SET
            completion_tokens = LENGTH(content) / 4,
            prompt_tokens     = 0,
            total_tokens      = LENGTH(content) / 4,
            cost_usd          = 0.0,
            token_estimate    = true
        WHERE
            role = 'assistant'
            AND total_tokens IS NULL
    """)


def downgrade() -> None:
    op.drop_column("messages", "token_estimate")
