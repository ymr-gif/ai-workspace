"""
rate_limiter.py
────────────────
Production-safe Redis sliding-window rate limiter.

Design goals:
- single Redis ownership source
- no mutable shared globals
- graceful Redis degradation
- fail-open strategy
- safe proxy/IP handling
- atomic Redis pipeline usage
"""

import logging
import time

from fastapi import Request, HTTPException, Depends
from jose import jwt as _jose_jwt
from redis.asyncio import Redis
from redis.exceptions import RedisError

from config import JWT_ALGORITHM, JWT_SECRET_KEY
from core.redis_client import get_redis

logger = logging.getLogger("rate_limiter")


# ─────────────────────────────────────────────
# CLIENT IDENTIFICATION
# ─────────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    """
    Safely extract client IP.

    Supports:
    - direct connections
    - nginx reverse proxy
    - load balancers
    """

    forwarded = request.headers.get("x-forwarded-for")

    if forwarded:
        return forwarded.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def get_key(request: Request) -> str:
    """
    Generate stable rate-limit key.

    Priority:
    1. request.state.current_user (set by get_current_user, avoids JWT re-decode)
    2. authenticated user (JWT sub claim)
    3. client IP
    """
    cu = getattr(request.state, "current_user", None)
    if cu is not None:
        return f"user:{cu.username}"

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            payload = _jose_jwt.decode(
                token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM],
                options={"verify_aud": False},
            )
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass

    return f"ip:{get_client_ip(request)}"


# ─────────────────────────────────────────────
# REDIS ACCESS
# ─────────────────────────────────────────────

def get_redis_client() -> Redis:
    """
    Centralized Redis accessor.

    Raises RuntimeError if Redis
    was not initialized during startup.
    """

    return get_redis()


# ─────────────────────────────────────────────
# RATE LIMITER
# ─────────────────────────────────────────────

def rate_limiter(
    limit: int,
    window: int,
    scope: str,
):
    """
    Sliding-window Redis rate limiter.

    Example:
        limit=60
        window=60
        scope="chat"

    Means:
        60 requests per 60 seconds
    """

    async def limiter(request: Request):

        # current unix timestamp
        now = time.time()

        # redis key
        key = f"rate:{scope}:{get_key(request)}"

        # ─────────────────────────────────────
        # REDIS ACCESS
        # ─────────────────────────────────────

        try:
            redis = get_redis_client()

        except RuntimeError:
            #
            # FAIL-OPEN STRATEGY
            #
            # If Redis is unavailable,
            # do NOT kill the API.
            #
            # Availability > rate limiting
            #
            logger.warning("[rate_limiter] fail-open (Redis unavailable) scope=%s key=%s", scope, key)
            return

        try:

            #
            # Sliding window algorithm
            #
            # Remove old entries
            # Add current request
            # Count active requests
            #

            async with redis.pipeline(transaction=True) as pipe:

                pipe.zremrangebyscore(
                    key,
                    0,
                    now - window,
                )

                pipe.zadd(
                    key,
                    {str(now): now},
                )

                pipe.zcard(key)

                pipe.expire(
                    key,
                    window,
                )

                results = await pipe.execute()

            #
            # pipeline results:
            # [removed, added, count, expire]
            #

            count = results[2]

            if count > limit:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                )

        except RedisError as e:
            #
            # FAIL-OPEN ON REDIS FAILURE
            #
            # Redis outages should not
            # bring down your API.
            #
            logger.warning("[rate_limiter] fail-open (RedisError) scope=%s key=%s err=%s", scope, key, e)
            return

    return limiter


# ─────────────────────────────────────────────
# FASTAPI DEPENDENCY WRAPPER
# ─────────────────────────────────────────────

def limit(
    limit: int,
    window: int,
    scope: str,
):
    """
    FastAPI dependency helper.

    Example:
        dependencies=[
            limit(60, 60, "chat")
        ]
    """

    return Depends(
        rate_limiter(
            limit=limit,
            window=window,
            scope=scope,
        )
    )


# ─────────────────────────────────────────────
# PER-MODEL RATE LIMITER (imperative)
# ─────────────────────────────────────────────

async def check_model_rate(full_model_name: str, username: str) -> None:
    """
    Apply per-model rate limit for an explicitly chosen model.
    Only called when user selects a specific model (override or locked).
    Fail-open on Redis unavailability.
    """
    from config import MODELS, MODEL_RATE_LIMITS

    model_key = next((k for k, v in MODELS.items() if v == full_model_name), None)
    if not model_key or model_key not in MODEL_RATE_LIMITS:
        return

    limit_count, window = MODEL_RATE_LIMITS[model_key]
    now = time.time()
    key = f"rate:model:{model_key}:user:{username}"

    try:
        redis = get_redis_client()
    except RuntimeError:
        logger.warning("[rate_limiter] fail-open (Redis unavailable) scope=model:%s user=%s", model_key, username)
        return

    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window)
            results = await pipe.execute()

        count = results[2]
        if count > limit_count:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {model_key} ({limit_count} req/min)",
            )
    except RedisError as e:
        logger.warning("[rate_limiter] fail-open (RedisError) scope=model:%s user=%s err=%s", model_key, username, e)
        return

