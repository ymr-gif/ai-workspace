"""Infra: Redis reachability + set/get/TTL roundtrip. Marker: infra."""
import asyncio
import uuid

import pytest

pytestmark = pytest.mark.infra


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_ping(redis_url):
    import redis.asyncio as aioredis

    async def _go():
        r = aioredis.from_url(redis_url)
        try:
            return await r.ping()
        finally:
            await r.aclose()

    assert _run(_go()) is True


def test_set_get_expire(redis_url):
    import redis.asyncio as aioredis

    key = f"verify:{uuid.uuid4().hex}"

    async def _go():
        r = aioredis.from_url(redis_url, decode_responses=True)
        try:
            await r.set(key, "ok", ex=30)
            val = await r.get(key)
            ttl = await r.ttl(key)
            await r.delete(key)
            gone = await r.get(key)
            return val, ttl, gone
        finally:
            await r.aclose()

    val, ttl, gone = _run(_go())
    assert val == "ok"
    assert 0 < ttl <= 30
    assert gone is None


def test_nx_lock_semantics(redis_url):
    """SET NX is the primitive behind the redis memory-lock backend."""
    import redis.asyncio as aioredis

    key = f"verify:lock:{uuid.uuid4().hex}"

    async def _go():
        r = aioredis.from_url(redis_url, decode_responses=True)
        try:
            first = await r.set(key, "a", nx=True, ex=10)
            second = await r.set(key, "b", nx=True, ex=10)
            await r.delete(key)
            return first, second
        finally:
            await r.aclose()

    first, second = _run(_go())
    assert first is True
    assert second is None  # already held → NX fails
