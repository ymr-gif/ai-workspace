import logging

from fastapi import APIRouter
from fastapi.responses import Response

from .prom_metrics import (
    REQUEST_COUNT,
    ERROR_COUNT,
    CACHE_HIT,
    CACHE_MISS,
    FALLBACK_COUNT,
    CIRCUIT_TRIPS,
    MODEL_USAGE,
    MODEL_LATENCY,
    REQUEST_LATENCY,
    metrics_output,
)

logger = logging.getLogger("metrics_api")
router = APIRouter()


# ─────────────────────────────────────────────
# HELPERS — read live values from prom objects
# ─────────────────────────────────────────────

def _counter(metric) -> float:
    try:
        return float(metric._value.get())
    except Exception:
        return 0.0


def _labeled_counter(metric, **labels) -> float:
    try:
        return float(metric.labels(**labels)._value.get())
    except Exception:
        return 0.0


def _safe_div(a: float, b: float) -> float:
    return round(a / b, 4) if b else 0.0


def _model_latency_stats(model: str) -> dict:
    try:
        h     = MODEL_LATENCY.labels(model=model)
        total = float(h._sum.get())
        count = float(h._count.get())
        avg   = round(total / count * 1000, 2) if count else 0.0
        return {"avg_latency_ms": avg, "observations": int(count)}
    except Exception:
        return {"avg_latency_ms": 0.0, "observations": 0}


def _all_model_names() -> list[str]:
    try:
        return [labels[0] for labels in MODEL_USAGE._metrics]
    except Exception:
        return []


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@router.get("/metrics/overview")
def overview():
    success  = _labeled_counter(REQUEST_COUNT, status="success")
    error    = _labeled_counter(REQUEST_COUNT, status="error")
    total    = success + error
    hits     = _counter(CACHE_HIT)
    misses   = _counter(CACHE_MISS)

    return {
        "total_requests":  int(total),
        "success_requests": int(success),
        "error_requests":  int(error),
        "error_rate":      _safe_div(error, total),
        "cache_hit_rate":  _safe_div(hits, hits + misses),
        "cache_hits":      int(hits),
        "cache_misses":    int(misses),
        "fallbacks":       int(_counter(FALLBACK_COUNT)),
        "circuit_trips":   int(_counter(CIRCUIT_TRIPS)),
    }


@router.get("/metrics/models")
def models():
    result = {}
    for model in _all_model_names():
        count   = _labeled_counter(MODEL_USAGE, model=model)
        latency = _model_latency_stats(model)
        result[model] = {
            "requests":      int(count),
            "avg_latency_ms": latency["avg_latency_ms"],
            "observations":  latency["observations"],
        }
    return result


@router.get("/metrics/latency")
def latency():
    try:
        h     = REQUEST_LATENCY
        total = float(h._sum.get())
        count = float(h._count.get())
        avg   = round(total / count * 1000, 2) if count else 0.0
        return {
            "avg_request_latency_ms": avg,
            "total_requests":         int(count),
        }
    except Exception:
        logger.exception("[metrics_api] latency read failed")
        return {"avg_request_latency_ms": 0.0, "total_requests": 0}


@router.get("/metrics/prometheus")
def prometheus_export():
    return Response(metrics_output(), media_type="text/plain")
