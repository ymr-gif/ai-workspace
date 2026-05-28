"""029 add fact_saliences JSONB column to user_memory

Revision ID: 029
Revises: 028
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_memory", sa.Column("fact_saliences", JSONB, nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("user_memory", "fact_saliences")
