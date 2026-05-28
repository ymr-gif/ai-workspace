"""026 system config

Revision ID: 026
Revises: 025
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op

revision     = "026"
down_revision = "025"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "system_config",
        sa.Column("key",        sa.String(64), primary_key=True),
        sa.Column("value",      sa.Text(),     nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("system_config")
