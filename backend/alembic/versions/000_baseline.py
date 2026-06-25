"""baseline — create the foundational tables (users, invitations, files, file_chunks)

These four tables were historically created by ``Base.metadata.create_all()`` in
``init_db()`` and never by a migration, so ``alembic upgrade head`` against a
*fresh* database failed at 001 (``conversations`` FK → ``users`` with no users
table). This baseline makes the migration chain self-sufficient from an empty DB.

Each table is created with its **original** columns only — later migrations add
the rest via unguarded ``add_column`` (e.g. users.api_key=022, cost_limit_usd=012,
cost_window_days=025, webhook_token=040, email=041, has_onboarded=046;
files.sha256_hash=016, chunk_*/embed_fail_count=030, media_type/ocr_text=045).
Creating those columns here would make the later ALTERs fail with duplicates.

Guarded with ``_table_exists`` so it is a no-op on databases already materialised
by ``create_all`` (existing dev/prod volumes stamped at head are unaffected).

Revision ID: 000
Revises:
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector


revision = "000"
down_revision = None
branch_labels = None
depends_on = None

# Frozen at the embedding dimension in use when file_chunks was introduced.
_EMBEDDING_DIM = 1024


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id",              sa.Integer(), primary_key=True),
            sa.Column("username",        sa.String(64), nullable=False),
            sa.Column("hashed_password", sa.String(256), nullable=False),
            sa.Column("role",            sa.String(32), server_default="user", nullable=False),
            sa.Column("is_active",       sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    if not _table_exists("invitations"):
        op.create_table(
            "invitations",
            sa.Column("id",            UUID(as_uuid=True), primary_key=True),
            sa.Column("token",         sa.String(64), nullable=False),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("email",         sa.String(254), nullable=True),
            sa.Column("used_by_id",    sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at",    sa.DateTime(timezone=True), nullable=True),
            sa.Column("used_at",       sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)
        op.create_index("ix_invitations_created_by_id", "invitations", ["created_by_id"])

    if not _table_exists("files"):
        op.create_table(
            "files",
            sa.Column("id",            UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id",       sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("filename",      sa.String(512), nullable=False),
            sa.Column("mime_type",     sa.String(128), nullable=False),
            sa.Column("size_bytes",    sa.Integer(), nullable=False),
            sa.Column("storage_path",  sa.String(1024), nullable=False, unique=True),
            sa.Column("upload_status", sa.String(32), server_default="uploaded", nullable=False),
            # Historical string column: only ever created by an old create_all. Migration
            # 018 migrates it (string→UUID FK) and 037 drops it. Present here so the chain
            # replays from an empty DB; gone by head, matching the current model.
            sa.Column("workspace_id",  sa.String(64), nullable=True),
            sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_files_user_id", "files", ["user_id"])
        op.create_index("ix_files_upload_status", "files", ["upload_status"])
        op.create_index("ix_files_workspace_id", "files", ["workspace_id"])

    if not _table_exists("file_chunks"):
        op.create_table(
            "file_chunks",
            sa.Column("id",          UUID(as_uuid=True), primary_key=True),
            sa.Column("file_id",     UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content",     sa.Text(), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("embedding",   Vector(_EMBEDDING_DIM), nullable=True),
            sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_file_chunks_file_id", "file_chunks", ["file_id"])


def downgrade():
    op.drop_table("file_chunks")
    op.drop_table("files")
    op.drop_table("invitations")
    op.drop_table("users")
