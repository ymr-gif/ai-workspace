import asyncio
import json
import logging
import time
import uuid

from core.redis_client import get_redis

STREAM_KEY      = "metrics_stream"
MAX_STREAM_LEN  = 100_000

logger = logging.getLogger("stream")


def _redis():
    try:
        return get_redis()
    except Exception:
        return None


async def _write(event: dict) -> None:
    redis = _redis()
    if redis is None:
        return
    try:
        await redis.xadd(STREAM_KEY, event, maxlen=MAX_STREAM_LEN, approximate=True)
    except Exception:
        pass


def emit(event_type: str, request_id: str, payload: dict) -> None:
    event = {
        "id":         str(uuid.uuid4()),
        "request_id": request_id,
        "type":       event_type,
        "timestamp":  str(time.time()),
        "payload":    json.dumps(payload, separators=(",", ":")),
    }
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_write(event))
    except RuntimeError:
        pass
