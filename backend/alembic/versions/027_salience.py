"""027 add salience columns to user_memory

Revision ID: 027
Revises: 026
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op

revision     = "027"
down_revision = "026"
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column("user_memory", sa.Column("salience",     sa.Float(),                    nullable=False, server_default="1.0"))
    op.add_column("user_memory", sa.Column("confidence",   sa.Float(),                    nullable=False, server_default="1.0"))
    op.add_column("user_memory", sa.Column("last_used_at", sa.DateTime(timezone=True),    nullable=True))


def downgrade():
    op.drop_column("user_memory", "last_used_at")
    op.drop_column("user_memory", "confidence")
    op.drop_column("user_memory", "salience")
