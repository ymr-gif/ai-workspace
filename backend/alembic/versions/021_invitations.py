"""invitations table for invite-gated registration

Revision ID: 021
Revises: 020
Create Date: 2026-05-27
"""
from alembic import op

revision      = "021"
down_revision = "020"
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS invitations (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            token         VARCHAR(64) NOT NULL UNIQUE,
            created_by_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            email         VARCHAR(254),
            used_by_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at    TIMESTAMPTZ,
            used_at       TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_invitations_token ON invitations(token)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invitations_created_by ON invitations(created_by_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_invitations_created_by")
    op.execute("DROP INDEX IF EXISTS ix_invitations_token")
    op.execute("DROP TABLE IF EXISTS invitations")
