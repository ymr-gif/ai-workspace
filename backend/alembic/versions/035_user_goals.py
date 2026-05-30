"""create user_goals table

Revision ID: 035
Revises: 034
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

revision      = "035"
down_revision = "034"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "user_goals",
        sa.Column("id",                      UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",                 sa.Integer(),       sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title",                   sa.String(200),     nullable=False),
        sa.Column("description",             sa.Text(),          nullable=True),
        sa.Column("status",                  sa.String(20),      nullable=False, server_default="active"),
        sa.Column("linked_conversation_ids",  postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at",              sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",              sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_goals_user_id", "user_goals", ["user_id"])


def downgrade():
    op.drop_table("user_goals")
