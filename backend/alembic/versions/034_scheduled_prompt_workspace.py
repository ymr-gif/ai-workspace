"""add workspace_id to scheduled_prompts

Revision ID: 034
Revises: 033
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = "034"
down_revision = "033"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        "scheduled_prompts",
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_scheduled_prompts_workspace_id", "scheduled_prompts", ["workspace_id"])


def downgrade():
    op.drop_index("ix_scheduled_prompts_workspace_id", table_name="scheduled_prompts")
    op.drop_column("scheduled_prompts", "workspace_id")
