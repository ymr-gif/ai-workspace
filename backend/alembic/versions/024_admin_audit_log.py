"""024 admin audit log

Revision ID: 024
Revises: 023
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision     = "024"
down_revision = "023"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "admin_audit_logs",
        sa.Column("id",             postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("admin_id",       sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action",         sa.String(64), nullable=False),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("detail",         postgresql.JSONB(), nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_admin_audit_logs_admin_id",       "admin_audit_logs", ["admin_id"])
    op.create_index("ix_admin_audit_logs_action",         "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_target_user_id", "admin_audit_logs", ["target_user_id"])
    op.create_index("ix_admin_audit_logs_created_at",     "admin_audit_logs", ["created_at"])


def downgrade():
    op.drop_table("admin_audit_logs")
