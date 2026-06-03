"""drop the workspace layer — workspaces + workspace_memory tables and workspace_id FKs

The workspace grouping layer was removed: sessions (conversations) are the only
organizer now. This drops the two tables and the nullable workspace_id FK columns
on conversations, files, and scheduled_prompts.

DESTRUCTIVE: workspace rows, workspace memory, and every workspace_id association
are dropped. The columns were nullable / SET NULL, so no child rows are deleted.
downgrade() recreates empty tables + columns but cannot restore the data.

Revision ID: 037
Revises: 036
Create Date: 2026-06-03
"""
from alembic import op

revision      = "037"
down_revision = "036"
branch_labels = None
depends_on    = None


def upgrade():
    # drop workspace_id FK columns from child tables
    op.execute("DROP INDEX IF EXISTS ix_conversations_workspace_id")
    op.execute("ALTER TABLE conversations DROP COLUMN IF EXISTS workspace_id")

    op.execute("DROP INDEX IF EXISTS ix_files_workspace_id")
    op.execute("ALTER TABLE files DROP COLUMN IF EXISTS workspace_id")

    op.execute("DROP INDEX IF EXISTS ix_scheduled_prompts_workspace_id")
    op.execute("ALTER TABLE scheduled_prompts DROP COLUMN IF EXISTS workspace_id")

    # drop workspace tables (workspace_memory FKs workspaces → drop it first)
    op.execute("DROP INDEX IF EXISTS ix_workspace_memory_workspace_id")
    op.execute("DROP TABLE IF EXISTS workspace_memory")
    op.execute("DROP INDEX IF EXISTS ix_workspaces_user_id")
    op.execute("DROP TABLE IF EXISTS workspaces")


def downgrade():
    # recreate empty tables + nullable columns (data is NOT restorable)
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

    op.execute("""
        CREATE TABLE IF NOT EXISTS workspace_memory (
            id              SERIAL PRIMARY KEY,
            workspace_id    UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
            content         TEXT,
            project_summary TEXT,
            version         INTEGER NOT NULL DEFAULT 0,
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_workspace_memory_workspace_id ON workspace_memory(workspace_id)")

    op.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_conversations_workspace_id ON conversations(workspace_id)")

    op.execute("ALTER TABLE files ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_files_workspace_id ON files(workspace_id)")

    op.execute("ALTER TABLE scheduled_prompts ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scheduled_prompts_workspace_id ON scheduled_prompts(workspace_id)")
