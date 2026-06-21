"""add UserNotificationPreferences and PushSubscription tables (Phase 3c)

Revision ID: 047
Revises: 046
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = "047"
down_revision = "046"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "user_notification_preferences",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("email_digest", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("email_scheduled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("email_insights", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("push_enabled", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("endpoint", sa.String(512), nullable=False),
        sa.Column("p256dh", sa.String(256), nullable=False),
        sa.Column("auth", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("push_subscriptions")
    op.drop_table("user_notification_preferences")
