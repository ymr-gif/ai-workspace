"""add is_archived and archived_at to conversations

Revision ID: 043
Revises: 042
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision      = "043"
down_revision = "042"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column("conversations",
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.text("false"))
    )
    op.add_column("conversations",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    op.drop_column("conversations", "archived_at")
    op.drop_column("conversations", "is_archived")
