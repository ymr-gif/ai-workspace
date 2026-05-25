"""add prompt_templates table

Revision ID: 014
Revises: 013
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prompt_templates",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",     sa.Integer(),        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name",        sa.String(100),      nullable=False),
        sa.Column("description", sa.Text(),           nullable=True),
        sa.Column("content",     sa.Text(),           nullable=False),
        sa.Column("is_shared",   sa.Boolean(),        nullable=False, server_default="false"),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_templates_user_id", "prompt_templates", ["user_id"])
    op.create_index("ix_prompt_templates_is_shared", "prompt_templates", ["is_shared"])


def downgrade():
    op.drop_table("prompt_templates")
