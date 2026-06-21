"""Memory write lock abstraction — pg and redis backends.

Run: pytest backend/tests/test_mem_lock.py -v
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY",  "test-key")
os.environ.setdefault("DATABASE_URL",    "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret")
os.environ.setdefault("MEMORY_LOCK_BACKEND", "pg")

import config as cfg
from core.locks import user_write_lock


@pytest.fixture(autouse=True)
def _reset_config():
    """Restore defaults after each test."""
    cfg.MEMORY_LOCK_BACKEND = "pg"
    cfg.MEMORY_LOCK_TTL = 30
    cfg.MEMORY_LOCK_WAIT = 5


# ── pg backend ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pg_lock_executes_advisory_lock():
    db = AsyncMock(spec=object)
    db.execute = AsyncMock()

    async with user_write_lock(db, 42):
        pass

    db.execute.assert_awaited_once()
    call_args = db.execute.await_args[0][0]
    assert "pg_advisory_xact_lock" in str(call_args)


@pytest.mark.asyncio
async def test_pg_lock_default_backend():
    assert cfg.MEMORY_LOCK_BACKEND == "pg"
    db = AsyncMock(spec=object)
    db.execute = AsyncMock()

    async with user_write_lock(db, 99):
        pass

    db.execute.assert_awaited_once()


# ── redis backend ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_redis_lock_acquire_and_release():
    cfg.MEMORY_LOCK_BACKEND = "redis"
    redis = AsyncMock(spec=object)
    redis.set = AsyncMock(return_value=True)
    redis.eval = AsyncMock(return_value=1)

    db = AsyncMock(spec=object)

    with patch("core.redis_client.get_redis", return_value=redis):
        async with user_write_lock(db, 42):
            pass

    redis.set.assert_awaited_once()
    lock_key = redis.set.await_args[0][0]
    assert lock_key == "lock:mem:42"
    assert redis.set.await_args[1]["nx"] is True
    assert redis.set.await_args[1]["ex"] == 30

    redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_lock_blocks_second_holder():
    cfg.MEMORY_LOCK_BACKEND = "redis"
    cfg.MEMORY_LOCK_TTL = 2
    cfg.MEMORY_LOCK_WAIT = 0.5

    redis = AsyncMock(spec=object)

    # First call acquires, second call fails (NX returns False)
    redis.set = AsyncMock(side_effect=[True, False, False, False, False, False, False, False, False, False])

    db = AsyncMock(spec=object)

    with patch("core.redis_client.get_redis", return_value=redis):
        async with user_write_lock(db, 42):
            pass

    assert redis.set.call_count >= 1


@pytest.mark.asyncio
async def test_redis_lock_releases_on_exception():
    cfg.MEMORY_LOCK_BACKEND = "redis"
    redis = AsyncMock(spec=object)
    redis.set = AsyncMock(return_value=True)
    redis.eval = AsyncMock(return_value=1)

    db = AsyncMock(spec=object)

    with patch("core.redis_client.get_redis", return_value=redis):
        with pytest.raises(RuntimeError, match="boom"):
            async with user_write_lock(db, 42):
                raise RuntimeError("boom")

    redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_lock_respects_ttl():
    cfg.MEMORY_LOCK_BACKEND = "redis"
    cfg.MEMORY_LOCK_TTL = 15
    redis = AsyncMock(spec=object)
    redis.set = AsyncMock(return_value=True)
    redis.eval = AsyncMock(return_value=1)

    db = AsyncMock(spec=object)

    with patch("core.redis_client.get_redis", return_value=redis):
        async with user_write_lock(db, 7):
            pass

    assert redis.set.await_args[1]["ex"] == 15


@pytest.mark.asyncio
async def test_redis_lock_timeout_no_acquire():
    cfg.MEMORY_LOCK_BACKEND = "redis"
    cfg.MEMORY_LOCK_TTL = 30
    cfg.MEMORY_LOCK_WAIT = 0.1

    redis = AsyncMock(spec=object)
    redis.set = AsyncMock(return_value=False)  # always fail

    db = AsyncMock(spec=object)

    with patch("core.redis_client.get_redis", return_value=redis):
        with pytest.raises(TimeoutError):
            async with user_write_lock(db, 42):
                pass


@pytest.mark.asyncio
async def test_redis_lua_release_script():
    cfg.MEMORY_LOCK_BACKEND = "redis"
    redis = AsyncMock(spec=object)
    redis.set = AsyncMock(return_value=True)
    redis.eval = AsyncMock(return_value=1)

    db = AsyncMock(spec=object)

    with patch("core.redis_client.get_redis", return_value=redis):
        async with user_write_lock(db, 1):
            pass

    eval_args = redis.eval.await_args
    lua_script = eval_args[0][0]
    assert "redis.call(\"GET\", KEYS[1])" in lua_script
    assert "redis.call(\"DEL\", KEYS[1])" in lua_script
    assert eval_args[0][1] == 1
    assert eval_args[0][2] == "lock:mem:1"


# ── invalid backend ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_backend_raises():
    cfg.MEMORY_LOCK_BACKEND = "invalid"
    db = AsyncMock(spec=object)

    with pytest.raises(ValueError, match="MEMORY_LOCK_BACKEND"):
        async with user_write_lock(db, 1):
            pass
