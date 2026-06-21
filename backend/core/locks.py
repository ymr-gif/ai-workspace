import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import config

logger = logging.getLogger("locks")

_LOCK_PREFIX = "lock:mem:"

_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


async def _acquire_redis_lock(redis, key: str, token: str, ttl: int, wait: float) -> bool:
    deadline = asyncio.get_event_loop().time() + wait
    delay = 0.05
    while True:
        acquired = await redis.set(key, token, nx=True, ex=ttl)
        if acquired:
            return True
        if asyncio.get_event_loop().time() >= deadline:
            return False
        await asyncio.sleep(delay)
        delay = min(delay * 2, 0.5)


async def _release_redis_lock(redis, key: str, token: str) -> None:
    try:
        await redis.eval(_RELEASE_SCRIPT, 1, key, token)
    except Exception:
        logger.exception("Failed to release redis lock %s", key)


@asynccontextmanager
async def user_write_lock(db: AsyncSession, user_id: int) -> AsyncIterator[None]:
    backend = config.MEMORY_LOCK_BACKEND
    if backend == "pg":
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": user_id})
        yield
    elif backend == "redis":
        from core.redis_client import get_redis

        redis = get_redis()
        token = str(uuid.uuid4())
        key = f"{_LOCK_PREFIX}{user_id}"
        ttl = config.MEMORY_LOCK_TTL
        wait = config.MEMORY_LOCK_WAIT
        acquired = await _acquire_redis_lock(redis, key, token, ttl, wait)
        if not acquired:
            raise TimeoutError(f"Could not acquire memory write lock for user {user_id}")
        try:
            yield
        finally:
            await _release_redis_lock(redis, key, token)
    else:
        raise ValueError(f"Unknown MEMORY_LOCK_BACKEND: {backend!r}")
