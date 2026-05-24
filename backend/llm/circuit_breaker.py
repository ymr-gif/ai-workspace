import logging
import time

from observability import metrics
from observability import observability
from observability import events

logger = logging.getLogger("circuit_breaker")

_THRESHOLD = 3
_COOLDOWN  = 30

_failures: dict[str, int]   = {}
_open:     dict[str, bool]  = {}
_open_time: dict[str, float] = {}


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
            await observability.publish_error_event(
                events.error_event(error_type="circuit_open", model=model)
            )
        except Exception:
            pass
        logger.warning("[circuit] opened model=%s", model)


def record_success(model: str) -> None:
    _failures[model] = 0
    _open.pop(model, None)
