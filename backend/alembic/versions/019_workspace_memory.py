"""workspace_memory table

Revision ID: 019
Revises: 018
Create Date: 2026-05-27
"""
from alembic import op

revision      = "019"
down_revision = "018"
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS workspace_memory (
            id            SERIAL PRIMARY KEY,
            workspace_id  UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
            content       TEXT,
            project_summary TEXT,
            version       INTEGER NOT NULL DEFAULT 0,
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_workspace_memory_workspace_id ON workspace_memory(workspace_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_workspace_memory_workspace_id")
    op.execute("DROP TABLE IF EXISTS workspace_memory")
