import json
import logging
import time
from typing import Optional

from redis.exceptions import RedisError

from config import USE_REDIS
from core.redis_client import get_redis
from cache.keys import make_key
from observability.metrics import record_cache_hit, record_cache_miss, record_cache_write
import cache.memory as memory

logger = logging.getLogger("cache")


def _redis():
    if not USE_REDIS:
        return None
    try:
        return get_redis()
    except Exception:
        return None


async def get_cached_response(
    message: str,
    *,
    model: str = "",
    history_tail: str = "",
    system_prompt: str = "",
) -> Optional[dict]:
    key   = make_key(message, model=model, history_tail=history_tail, system_prompt=system_prompt)
    redis = _redis()

    if redis:
        try:
            data = await redis.get(key)
            if data:
                record_cache_hit()
                return json.loads(data)
            record_cache_miss()
            return None
        except RedisError as e:
            logger.warning("[cache] Redis read failed: %s", e)

    result = memory.get(key)
    if result:
        record_cache_hit()
    else:
        record_cache_miss()
    return result


async def set_cached_response(
    message: str,
    response: dict,
    ttl: int = 3600,
    *,
    model: str = "",
    history_tail: str = "",
    system_prompt: str = "",
) -> None:
    key     = make_key(message, model=model, history_tail=history_tail, system_prompt=system_prompt)
    payload = {
        "response":  response.get("response"),
        "model":     response.get("model"),
        "timestamp": time.time(),
    }

    redis = _redis()
    if redis:
        try:
            await redis.set(key, json.dumps(payload), ex=ttl)
            record_cache_write()
            return
        except RedisError as e:
            logger.warning("[cache] Redis write failed: %s", e)

    memory.set(key, payload, ttl)
    record_cache_write()


def get_cache_stats() -> dict:
    return {
        "memory_keys": memory.size(),
        "mode":        "redis+fallback" if _redis() else "memory-only",
    }
