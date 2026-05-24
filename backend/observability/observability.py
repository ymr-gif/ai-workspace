import json
import logging
from typing import Any, Dict, Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

from core.redis_client import get_redis
from config import OBSERVABILITY_ENABLED, METRICS_STREAM, METRICS_STREAM_MAXLEN

logger = logging.getLogger("observability")


def _redis() -> Optional[Redis]:
    try:
        return get_redis()
    except Exception:
        return None


def is_ready() -> bool:
    return OBSERVABILITY_ENABLED and _redis() is not None


async def publish_event(event: Dict[str, Any]) -> bool:
    if not OBSERVABILITY_ENABLED:
        return False
    redis = _redis()
    if not redis:
        return False
    try:
        await redis.xadd(
            name=METRICS_STREAM,
            fields={"data": json.dumps(event, default=str)},
            maxlen=METRICS_STREAM_MAXLEN,
            approximate=True,
        )
        return True
    except RedisError as e:
        logger.warning("[observability] Redis error: %s", e)
        return False
    except Exception:
        logger.exception("[observability] unexpected publish failure")
        return False


async def publish_request_event(event: Dict[str, Any])         -> bool: return await publish_event(event)
async def publish_model_event(event: Dict[str, Any])           -> bool: return await publish_event(event)
async def publish_cache_event(event: Dict[str, Any])           -> bool: return await publish_event(event)
async def publish_error_event(event: Dict[str, Any])           -> bool: return await publish_event(event)
async def publish_circuit_breaker_event(event: Dict[str, Any]) -> bool: return await publish_event(event)
