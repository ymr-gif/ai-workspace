"""memory_conflicts table

Revision ID: 028
Revises: 027
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_conflicts",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",       sa.Integer(),       sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_a",        sa.Text(),          nullable=False),
        sa.Column("fact_b",        sa.Text(),          nullable=False),
        sa.Column("conflict_type", sa.String(32),      nullable=False),
        sa.Column("resolution",    sa.String(32),      nullable=True, server_default="unresolved"),
        sa.Column("resolved_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memory_conflicts_user_id",         "memory_conflicts", ["user_id"])
    op.create_index("ix_memory_conflicts_user_resolution", "memory_conflicts", ["user_id", "resolution"])


def downgrade() -> None:
    op.drop_index("ix_memory_conflicts_user_resolution", "memory_conflicts")
    op.drop_index("ix_memory_conflicts_user_id",         "memory_conflicts")
    op.drop_table("memory_conflicts")
