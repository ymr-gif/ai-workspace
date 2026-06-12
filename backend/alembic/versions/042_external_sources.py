"""create external_sources table

Revision ID: 042
Revises: 041
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision      = "042"
down_revision = "041"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "external_sources",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id",       sa.Integer,  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("connector_type", sa.String(32),  nullable=False),
        sa.Column("display_name",  sa.String(200),  nullable=True),
        sa.Column("resource_id",   sa.String(512),  nullable=True),
        sa.Column("credentials",   JSONB, nullable=True),
        sa.Column("status",        sa.String(16),  nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error",         sa.Text, nullable=True),
        sa.Column("last_sync_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_external_sources_user_id", "external_sources", ["user_id"])
    op.create_unique_index(
        "ix_external_sources_user_connector_resource",
        "external_sources", ["user_id", "connector_type", "resource_id"]
    )


def downgrade():
    op.drop_index("ix_external_sources_user_connector_resource")
    op.drop_index("ix_external_sources_user_id")
    op.drop_table("external_sources")
