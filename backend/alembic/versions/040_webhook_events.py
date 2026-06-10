"""add webhook_token to users, create webhook_events table

Revision ID: 040
Revises: 039
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision      = "040"
down_revision = "039"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("webhook_token", UUID(as_uuid=True), nullable=True, unique=True),
    )
    op.create_index("ix_users_webhook_token", "users", ["webhook_token"])

    op.create_table(
        "webhook_events",
        sa.Column("id",           UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id",      sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type",   sa.String(64), nullable=False),
        sa.Column("payload",      JSONB, nullable=False),
        sa.Column("status",       sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error",        sa.Text, nullable=True),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("webhook_events")
    op.drop_index("ix_users_webhook_token")
    op.drop_column("users", "webhook_token")
