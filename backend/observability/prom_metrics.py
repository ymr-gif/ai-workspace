import os

from prometheus_client import (
    Counter,
    CollectorRegistry,
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

STREAM_INTERRUPTIONS = Counter(
    "stream_interruptions_total",
    "Streams that delivered partial content then failed",
)

ALL_MODELS_FAILED = Counter(
    "all_models_failed_total",
    "Requests where every model in the fallback chain failed",
)

ARQ_JOB_FAILED = Counter(
    "arq_job_failed_total",
    "ARQ jobs permanently dropped after max retries",
    ["job_type"],
)

# ─────────────────────────────────────────────
# SNAPSHOT EXPORT
# ─────────────────────────────────────────────

def _collect() -> bytes:
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        from prometheus_client import multiprocess
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest()


def export_metrics() -> bytes:
    return _collect()


def metrics_output() -> bytes:
    return _collect()