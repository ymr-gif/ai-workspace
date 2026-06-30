import asyncio
import logging

import httpx

import llm.client as llm_client
import config

logger = logging.getLogger("embeddings")

# The NIM embedder (nv-embedqa-e5-v5) returns intermittent 5xx under load — a single failed
# embed nulls query_emb and silently disables the connector-intent latch for that turn
# (embed_status="failed"). Retry transient failures (5xx + network/timeout) with short
# exponential backoff; fail fast on 4xx (bad request / auth won't recover) and on the final
# attempt. Backoff: 0.5s, 1s, 2s → ~3.5s worst case before giving up. Latency is only paid when
# a failure actually occurs, so healthy turns are unaffected.
_MAX_ATTEMPTS = 4
_BACKOFF_BASE = 0.5


async def embed(text: str, input_type: str = "passage") -> list[float] | None:
    if llm_client.client is None:
        logger.error("[embeddings] HTTP client not initialized")
        return None

    headers = {"Content-Type": "application/json"}
    if config.NVIDIA_API_KEY:
        headers["Authorization"] = f"Bearer {config.NVIDIA_API_KEY}"
    payload = {
        "model":           config.MODEL_EMBEDDING,
        "input":           [text[:2000]],
        "input_type":      input_type,
        "encoding_format": "float",
    }

    for attempt in range(_MAX_ATTEMPTS):
        last = attempt == _MAX_ATTEMPTS - 1
        try:
            resp = await llm_client.client.post(
                config.NIM_EMBEDDING_URL, headers=headers, json=payload, timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status < 500 or last:
                logger.error("[embeddings] embed failed (http %s, attempt %d/%d): %s",
                             status, attempt + 1, _MAX_ATTEMPTS, e)
                return None
            logger.warning("[embeddings] embed http %s — retry %d/%d", status, attempt + 1, _MAX_ATTEMPTS)
        except httpx.TransportError as e:   # network + timeouts (TimeoutException subclasses this)
            if last:
                logger.error("[embeddings] embed failed (transport, attempt %d/%d): %s",
                             attempt + 1, _MAX_ATTEMPTS, e)
                return None
            logger.warning("[embeddings] embed transient %s — retry %d/%d",
                           type(e).__name__, attempt + 1, _MAX_ATTEMPTS)
        except Exception as e:              # malformed JSON / unexpected — don't spin
            logger.error("[embeddings] embed failed (non-retryable): %s", e)
            return None
        await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))

    return None
