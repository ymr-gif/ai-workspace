from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ─────────────────────────────────────────────
# CORE METRICS
# ─────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total API requests",
    ["status"],
)

ERROR_COUNT = Counter(
    "api_errors_total",
    "Total API errors",
    ["type"],
)

CACHE_HIT = Counter(
    "cache_hits_total",
    "Cache hits",
)

CACHE_MISS = Counter(
    "cache_misses_total",
    "Cache misses",
)

CACHE_WRITE = Counter(
    "cache_writes_total",
    "Cache writes",
)

MODEL_LATENCY = Histogram(
    "model_latency_seconds",
    "Model latency",
    ["model"],
)

REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "Request latency",
)

FALLBACK_COUNT = Counter(
    "fallback_total",
    "Fallback usage count",
)

CIRCUIT_TRIPS = Counter(
    "circuit_breaker_trips_total",
    "Circuit breaker trips",
)

MODEL_USAGE = Counter(
    "model_usage_total",
    "Model usage",
    ["model"],
)

LATENCY = Histogram(
    "ai_request_latency_seconds",
    "AI request latency",
    buckets=(0.1, 0.3, 0.5, 1, 2, 5, 10)
)

# ─────────────────────────────────────────────
# SNAPSHOT EXPORT
# ─────────────────────────────────────────────

def export_metrics() -> bytes:
    return generate_latest()


def metrics_output() -> bytes:
    return generate_latest()