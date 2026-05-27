"""user_insights table

Revision ID: 023
Revises: 022
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = "023"
down_revision = "022"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "user_insights",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id",    sa.Integer,  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("content",    sa.Text,     nullable=False),
        sa.Column("is_read",    sa.Boolean,  nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("user_insights")
