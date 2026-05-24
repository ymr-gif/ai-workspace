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

import time

from fastapi import Request, HTTPException, Depends
from redis.asyncio import Redis
from redis.exceptions import RedisError

from core.redis_client import get_redis


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
    1. authenticated user
    2. client IP
    """

    user = getattr(request.state, "user", None)

    if user and getattr(user, "username", None):
        return f"user:{user.username}"

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

        except RedisError:
            #
            # FAIL-OPEN ON REDIS FAILURE
            #
            # Redis outages should not
            # bring down your API.
            #
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

