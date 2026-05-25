"""add scheduled_prompts and scheduled_prompt_runs tables

Revision ID: 015
Revises: 014
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scheduled_prompts",
        sa.Column("id",             UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",        sa.Integer(),       sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name",           sa.String(100),     nullable=False),
        sa.Column("prompt",         sa.Text(),          nullable=False),
        sa.Column("cron_expr",      sa.String(100),     nullable=False),
        sa.Column("model_override", sa.String(100),     nullable=True),
        sa.Column("is_active",      sa.Boolean(),       nullable=False, server_default="true"),
        sa.Column("last_run_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scheduled_prompts_user_id",   "scheduled_prompts", ["user_id"])
    op.create_index("ix_scheduled_prompts_is_active", "scheduled_prompts", ["is_active"])

    op.create_table(
        "scheduled_prompt_runs",
        sa.Column("id",                  UUID(as_uuid=True), primary_key=True),
        sa.Column("scheduled_prompt_id", UUID(as_uuid=True), sa.ForeignKey("scheduled_prompts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at",          sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("status",              sa.String(20),  nullable=False, server_default="running"),
        sa.Column("output_file_id",      UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error",               sa.Text(),      nullable=True),
    )
    op.create_index("ix_scheduled_prompt_runs_schedule_id", "scheduled_prompt_runs", ["scheduled_prompt_id"])


def downgrade():
    op.drop_table("scheduled_prompt_runs")
    op.drop_table("scheduled_prompts")
