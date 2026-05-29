import logging
import time

from observability import metrics
from observability import observability
from observability import events

logger = logging.getLogger("circuit_breaker")

_THRESHOLD = 5
_COOLDOWN  = 90

_failures: dict[str, int]    = {}
_open:     dict[str, bool]   = {}
_open_time: dict[str, float] = {}


def _redis_key(model: str) -> str:
    return f"cb:open:{model}"


def is_open(model: str) -> bool:
    if model not in _open:
        return False
    if time.time() - _open_time[model] > _COOLDOWN:
        _open.pop(model, None)
        _failures[model] = 0
        logger.info("[circuit] reset model=%s", model)
        return False
    return True


async def record_failure(model: str) -> None:
    _failures[model] = _failures.get(model, 0) + 1
    if _failures[model] >= _THRESHOLD:
        _open[model]      = True
        _open_time[model] = time.time()
        metrics.record_circuit_trip(model)
        try:
            from config import USE_REDIS
            if USE_REDIS:
                from core.redis_client import get_redis
                await get_redis().set(_redis_key(model), "1", ex=_COOLDOWN)
        except Exception:
            pass
        try:
            await observability.publish_error_event(
                events.error_event(error_type="circuit_open", model=model)
            )
        except Exception:
            pass
        logger.warning("[circuit] opened model=%s", model)


def record_success(model: str) -> None:
    _failures[model] = 0
    _open.pop(model, None)
    try:
        from config import USE_REDIS
        if USE_REDIS:
            import asyncio
            from core.redis_client import get_redis
            asyncio.get_event_loop().create_task(get_redis().delete(_redis_key(model)))
    except Exception:
        pass


async def restore_circuit_state() -> None:
    try:
        from config import USE_REDIS, MODELS
        if not USE_REDIS:
            return
        from core.redis_client import get_redis
        r = get_redis()
        for model_str in MODELS.values():
            if await r.exists(_redis_key(model_str)):
                _open[model_str]      = True
                _open_time[model_str] = time.time()
                logger.warning("[circuit] restored open state for model=%s", model_str)
    except Exception as e:
        logger.warning("[circuit] restore_circuit_state failed: %s", e)
