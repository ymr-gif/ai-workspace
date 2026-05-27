"""workspaces table; migrate files.workspace_id string→UUID FK; add conversations.workspace_id

Revision ID: 018
Revises: 017
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = "018"
down_revision = "017"
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name          VARCHAR(120) NOT NULL,
            description   TEXT,
            system_prompt TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_workspaces_user_id ON workspaces(user_id)")

    # Seed: one "Default" workspace per user + named workspaces for existing string workspace_ids
    op.execute("""
        INSERT INTO workspaces (id, user_id, name, created_at, updated_at)
        SELECT gen_random_uuid(), ws.user_id, ws.ws_name, now(), now()
        FROM (
            SELECT DISTINCT user_id, workspace_id AS ws_name
            FROM files
            WHERE workspace_id IS NOT NULL
            UNION
            SELECT id AS user_id, 'Default' AS ws_name
            FROM users
        ) AS ws
    """)

    # Add UUID FK column to files
    op.execute("ALTER TABLE files ADD COLUMN workspace_uuid UUID REFERENCES workspaces(id) ON DELETE SET NULL")

    # Link files with a named workspace_id to the matching workspace
    op.execute("""
        UPDATE files f
        SET workspace_uuid = w.id
        FROM workspaces w
        WHERE w.user_id = f.user_id
          AND w.name    = f.workspace_id
          AND f.workspace_id IS NOT NULL
    """)

    # Link files with no workspace_id to the user's Default workspace
    op.execute("""
        UPDATE files f
        SET workspace_uuid = w.id
        FROM workspaces w
        WHERE w.user_id = f.user_id
          AND w.name    = 'Default'
          AND f.workspace_id IS NULL
    """)

    # Drop old string column, rename UUID column
    op.execute("DROP INDEX IF EXISTS ix_files_workspace_id")
    op.execute("ALTER TABLE files DROP COLUMN workspace_id")
    op.execute("ALTER TABLE files RENAME COLUMN workspace_uuid TO workspace_id")
    op.execute("CREATE INDEX ix_files_workspace_id ON files(workspace_id)")

    # Add workspace_id to conversations; assign all existing convs to Default workspace
    op.execute("ALTER TABLE conversations ADD COLUMN workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL")
    op.execute("""
        UPDATE conversations c
        SET workspace_id = w.id
        FROM workspaces w
        WHERE w.user_id = c.user_id
          AND w.name    = 'Default'
    """)
    op.execute("CREATE INDEX ix_conversations_workspace_id ON conversations(workspace_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_conversations_workspace_id")
    op.execute("ALTER TABLE conversations DROP COLUMN IF EXISTS workspace_id")

    op.execute("DROP INDEX IF EXISTS ix_files_workspace_id")
    op.execute("ALTER TABLE files ADD COLUMN workspace_str VARCHAR(64)")
    op.execute("""
        UPDATE files f
        SET workspace_str = w.name
        FROM workspaces w
        WHERE w.id = f.workspace_id AND w.name != 'Default'
    """)
    op.execute("ALTER TABLE files DROP COLUMN workspace_id")
    op.execute("ALTER TABLE files RENAME COLUMN workspace_str TO workspace_id")
    op.execute("CREATE INDEX ix_files_workspace_id ON files(workspace_id)")

    op.execute("DROP INDEX IF EXISTS ix_workspaces_user_id")
    op.execute("DROP TABLE IF EXISTS workspaces")
