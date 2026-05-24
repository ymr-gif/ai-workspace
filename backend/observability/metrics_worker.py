"""
metrics_worker.py
──────────────────
Redis Streams → Metrics Aggregation Worker (STABLE VERSION)
"""

import asyncio
import json
import logging
from collections import defaultdict, deque

from redis.exceptions import ResponseError
from core.redis_client import get_redis, init_redis

logger = logging.getLogger("metrics_worker")


# ─────────────────────────────────────────────
# STREAM CONFIG
# ─────────────────────────────────────────────

STREAM_KEY = "metrics_stream"
GROUP = "metrics_group"
CONSUMER = "worker-1"


# ─────────────────────────────────────────────
# METRICS STATE
# ─────────────────────────────────────────────

metrics_store = {
    "requests": 0,
    "errors": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "cache_writes": 0,
    "model_calls": defaultdict(int),
    "request_latency": deque(maxlen=1000),
    "model_latency": deque(maxlen=1000),
    "fallbacks": 0,
    "circuit_trips": 0,
}


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────

async def init():
    """
    Worker Redis bootstrap (process-local).
    """

    # IMPORTANT: initialize Redis for THIS process
    init_redis()

    redis = get_redis()

    try:
        await redis.xgroup_create(
            STREAM_KEY,
            GROUP,
            id="0",
            mkstream=True,
        )
        logger.info("[worker] created consumer group")

    except Exception as e:
        if "BUSYGROUP" in str(e):
            logger.info("[worker] group already exists")
        else:
            raise

# ─────────────────────────────────────────────
# EVENT PROCESSING
# ─────────────────────────────────────────────

def process_event(data: dict):

    try:
        # Redis streams return bytes → normalize safely
        raw = data.get(b"data") or data.get("data")

        if isinstance(raw, bytes):
            raw = raw.decode()

        payload = json.loads(raw)

    except Exception as e:
        logger.warning(f"[worker] bad event: {e}")
        return

    event_type = payload.get("type")

    # ── REQUEST ─────────────────────────────
    if event_type == "request":
        metrics_store["requests"] += 1

        latency = payload.get("latency_ms")
        if latency:
            metrics_store["request_latency"].append(latency)

        if payload.get("fallback_used"):
            metrics_store["fallbacks"] += 1

    # ── ERROR ───────────────────────────────
    elif event_type == "error":
        metrics_store["errors"] += 1

    # ── CACHE ────────────────────────────────
    elif event_type == "cache":
        action = payload.get("action")

        if action == "hit":
            metrics_store["cache_hits"] += 1
        elif action == "miss":
            metrics_store["cache_misses"] += 1
        elif action == "write":
            metrics_store["cache_writes"] += 1

    # ── MODEL ────────────────────────────────
    elif event_type == "model":
        model = payload.get("model", "unknown")
        metrics_store["model_calls"][model] += 1

        latency = payload.get("latency_ms")
        if latency:
            metrics_store["model_latency"].append(latency)

    # ── CIRCUIT ──────────────────────────────
    elif event_type == "circuit":
        metrics_store["circuit_trips"] += 1


# ─────────────────────────────────────────────
# CONSUME LOOP
# ─────────────────────────────────────────────

async def consume():

    redis = get_redis()

    while True:

        try:
            messages = await redis.xreadgroup(
                GROUP,
                CONSUMER,
                {STREAM_KEY: ">"},
                count=50,
                block=2000,
            )

            if not messages:
                continue

            for stream, events in messages:
                for msg_id, data in events:

                    process_event(data)

                    await redis.xack(
                        STREAM_KEY,
                        GROUP,
                        msg_id,
                    )

        except Exception as e:
            logger.warning(f"[worker] stream error: {e}")
            await asyncio.sleep(1)


# ─────────────────────────────────────────────
# SNAPSHOT
# ─────────────────────────────────────────────

def snapshot():

    req_latency = list(metrics_store["request_latency"])

    model_latency = list(metrics_store["model_latency"])

    avg_req = sum(req_latency) / len(req_latency) if req_latency else 0
    avg_model = sum(model_latency) / len(model_latency) if model_latency else 0

    return {
        "requests": metrics_store["requests"],
        "errors": metrics_store["errors"],
        "cache_hits": metrics_store["cache_hits"],
        "cache_misses": metrics_store["cache_misses"],
        "cache_writes": metrics_store["cache_writes"],
        "fallbacks": metrics_store["fallbacks"],
        "circuit_trips": metrics_store["circuit_trips"],
        "avg_request_latency_ms": round(avg_req, 2),
        "avg_model_latency_ms": round(avg_model, 2),
        "model_calls": dict(metrics_store["model_calls"]),
    }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

async def main():
    await init()
    logger.info("[worker] started")
    await consume()


if __name__ == "__main__":
    asyncio.run(main())