"""Infra: Alembic migration integrity (+ applied-version check when a DB is reachable).

Marker: infra (opt-in RUN_INFRA=1). The single-head check needs no DB; the applied-head
check runs only when DATABASE_URL points at a reachable Postgres.
"""
import os

import pytest

pytestmark = pytest.mark.infra

_HERE = os.path.dirname(__file__)
_BACKEND = os.path.abspath(os.path.join(_HERE, "..", ".."))


def _alembic_cfg():
    from alembic.config import Config

    cfg = Config(os.path.join(_BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND, "alembic"))
    return cfg


def test_single_head():
    """A linear history — exactly one head — so `upgrade head` is unambiguous."""
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_cfg())
    heads = script.get_heads()
    assert len(heads) == 1, f"expected one migration head, found {heads}"


def test_revision_count_reasonable():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_cfg())
    revs = list(script.walk_revisions())
    # codebase ships 47 migrations (047_*); guard against an accidental truncation
    assert len(revs) >= 47, f"only {len(revs)} revisions found"


def test_applied_head_matches_script(db_dsn):
    """The live DB is migrated all the way to the script head."""
    import asyncpg

    from alembic.script import ScriptDirectory

    script_head = ScriptDirectory.from_config(_alembic_cfg()).get_current_head()

    async def _check():
        conn = await asyncpg.connect(db_dsn)
        try:
            applied = await conn.fetchval("SELECT version_num FROM alembic_version")
        finally:
            await conn.close()
        return applied

    import asyncio

    applied = asyncio.get_event_loop().run_until_complete(_check())
    assert applied == script_head, f"DB at {applied}, script head {script_head} — run `alembic upgrade head`"
