import time

from observability.stream import emit
from .prom_metrics import (
    CACHE_HIT,
    CACHE_MISS,
    CACHE_WRITE,
    CIRCUIT_TRIPS,
    FALLBACK_COUNT,
)


def record_request_start() -> float:
    return time.monotonic()


def record_request_end(
    start:         float,
    model:         str,
    status:        str,
    cache_hit:     bool = False,
    error_type:    str | None = None,
    fallback_used: bool = False,
) -> float:
    latency_ms = (time.monotonic() - start) * 1000
    emit("request", "system", {
        "model":         model,
        "status":        status,
        "latency_ms":    round(latency_ms, 2),
        "cache_hit":     cache_hit,
        "error_type":    error_type,
        "fallback_used": fallback_used,
    })
    return latency_ms


def record_cache_hit()              -> None: CACHE_HIT.inc()
def record_cache_miss()             -> None: CACHE_MISS.inc()
def record_cache_write()            -> None: CACHE_WRITE.inc()
def record_circuit_trip(model: str) -> None: CIRCUIT_TRIPS.inc()
def record_fallback()               -> None: FALLBACK_COUNT.inc()
