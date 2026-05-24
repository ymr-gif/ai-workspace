"""
events.py
─────────
Central observability event schemas/constants.

Used by:
- observability.py
- router.py
- service.py
- cache.py
- metrics_worker.py

Purpose:
- Prevent schema drift
- Standardize Redis Stream payloads
- Centralize event type naming
"""

from typing import Dict, Any
import time


# ──────────────────────────────────────────────────────────────────────────────
# Event type constants
# ──────────────────────────────────────────────────────────────────────────────

REQUEST_EVENT = "request"
MODEL_EVENT = "model"
CACHE_EVENT = "cache"
ERROR_EVENT = "error"
CIRCUIT_BREAKER_EVENT = "circuit_breaker"


# ──────────────────────────────────────────────────────────────────────────────
# Base event helper
# ──────────────────────────────────────────────────────────────────────────────

def base_event(event_type: str) -> Dict[str, Any]:
    """
    Shared metadata attached to all events.
    """
    return {
        "event_type": event_type,
        "timestamp": time.time(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Request events
# ──────────────────────────────────────────────────────────────────────────────

def request_event(
    request_id: str,
    model: str = "unknown",
    latency_ms: float = 0,
    status: str = "pending",
    cache_hit: bool = False,
    fallback_used: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    event = base_event(REQUEST_EVENT)

    event.update({
        "request_id": request_id,
        "model": model,
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "cache_hit": cache_hit,
        "fallback_used": fallback_used,
    })

    return event


# ──────────────────────────────────────────────────────────────────────────────
# Model events
# ──────────────────────────────────────────────────────────────────────────────

def model_event(
    model: str,
    latency_ms: float,
    success: bool,
) -> Dict[str, Any]:
    event = base_event(MODEL_EVENT)

    event.update({
        "model": model,
        "latency_ms": round(latency_ms, 2),
        "success": success,
    })

    return event


# ──────────────────────────────────────────────────────────────────────────────
# Cache events
# ──────────────────────────────────────────────────────────────────────────────

def cache_event(
    operation: str,   # "hit" | "miss" | "write"
) -> Dict[str, Any]:
    event = base_event(CACHE_EVENT)

    event.update({
        "operation": operation,
    })

    return event


# ──────────────────────────────────────────────────────────────────────────────
# Error events
# ──────────────────────────────────────────────────────────────────────────────

def error_event(
    error_type: str,
    model: str = "unknown",
) -> Dict[str, Any]:
    event = base_event(ERROR_EVENT)

    event.update({
        "error_type": error_type,
        "model": model,
    })

    return event


# ──────────────────────────────────────────────────────────────────────────────
# Circuit breaker events
# ──────────────────────────────────────────────────────────────────────────────

def circuit_breaker_event(
    model: str,
    failures: int,
) -> Dict[str, Any]:
    event = base_event(CIRCUIT_BREAKER_EVENT)

    event.update({
        "model": model,
        "failures": failures,
    })

    return event