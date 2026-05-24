from redis.asyncio import Redis
from redis.exceptions import RedisError
from config import REDIS_URL

_redis: Redis | None = None


# ─────────────────────────────────────────────
# INTERNAL CONNECTOR
# ─────────────────────────────────────────────

def _create_redis() -> Redis:
    return Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        health_check_interval=30,  # keeps connection alive
    )


# ─────────────────────────────────────────────
# INIT (explicit)
# ─────────────────────────────────────────────

def init_redis() -> Redis:
    global _redis
    _redis = _create_redis()
    return _redis


# ─────────────────────────────────────────────
# SELF-HEALING ACCESSOR
# ─────────────────────────────────────────────

def get_redis() -> Redis:
    global _redis

    try:
        # Case 1: not created yet
        if _redis is None:
            _redis = _create_redis()

        return _redis

    except RedisError:
        # Case 2: broken connection → recreate
        _redis = _create_redis()
        return _redis