"""Infra: Postgres + pgvector reachability and schema sanity. Marker: infra."""
import asyncio

import pytest

pytestmark = pytest.mark.infra


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_connect_and_select(db_dsn):
    import asyncpg

    async def _go():
        conn = await asyncpg.connect(db_dsn)
        try:
            return await conn.fetchval("SELECT 1")
        finally:
            await conn.close()

    assert _run(_go()) == 1


def test_pgvector_extension_installed(db_dsn):
    import asyncpg

    async def _go():
        conn = await asyncpg.connect(db_dsn)
        try:
            return await conn.fetchval("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        finally:
            await conn.close()

    assert _run(_go()) == 1, "pgvector extension not installed"


def test_core_tables_exist(db_dsn):
    import asyncpg

    async def _go():
        conn = await asyncpg.connect(db_dsn)
        try:
            rows = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
        finally:
            await conn.close()
        return {r["tablename"] for r in rows}

    tables = _run(_go())
    for expected in ("users", "conversations", "messages", "files", "file_chunks", "alembic_version"):
        assert expected in tables, f"missing table: {expected}"


def test_message_embedding_dim_is_1024(db_dsn):
    """The embedding column must stay 1024-d (changing it forces a full re-embed)."""
    import asyncpg

    async def _go():
        conn = await asyncpg.connect(db_dsn)
        try:
            # vector typmod encodes the dimension; format_type renders it as vector(N)
            return await conn.fetchval(
                """
                SELECT format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'message_embeddings' AND a.attname = 'embedding'
                """
            )
        finally:
            await conn.close()

    rendered = _run(_go())
    if rendered is None:
        pytest.skip("message_embeddings.embedding column not found on target")
    assert "1024" in rendered, f"embedding dim changed: {rendered}"
