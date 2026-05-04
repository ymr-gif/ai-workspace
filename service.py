"""
service.py
──────────
Core AI service layer

Responsibilities:
- Message routing (fast + future embedding support)
- Model selection
- NIM API calls
- Retry + fallback logic
- Response normalization

NO FastAPI code here.
"""

import asyncio
import time
import logging
import httpx

from config import (
    MODELS,
    FALLBACK_ORDER,
    NVIDIA_API_KEY,
    NIM_URL,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger("service")


# ──────────────────────────────────────────────────────────────────────────────
# 1. ROUTING LAYER (FAST + EMBEDDING READY)
# ──────────────────────────────────────────────────────────────────────────────

def classify_message_fast(message: str) -> str:
    """
    Cheap heuristic routing (no API calls).

    Phase 2 (future): replace or augment with embedding similarity routing.
    Plug-in point → route_message() below.
    """
    msg = message.lower()

    if any(k in msg for k in ["code", "python", "bug", "error", "function", "api"]):
        return "coder"

    if any(k in msg for k in ["why", "explain", "analyze", "compare", "reason"]):
        return "reasoning"

    return "llama"


async def route_message(message: str, request_id: str) -> str:
    """
    Main routing entry point.

    Phase 1: deterministic keyword routing (active).
    Phase 2 (future): embedding similarity routing — swap classify_message_fast()
                      here without touching anything else.
    """
    choice = classify_message_fast(message)

    logger.info(f"[service] rid={request_id} route={choice}")

    return MODELS.get(choice, MODELS["llama"])


# ──────────────────────────────────────────────────────────────────────────────
# 2. NIM API CALL
# ──────────────────────────────────────────────────────────────────────────────

async def call_nim(
    model: str,
    messages: list[dict],
    *,
    max_tokens: int = 512,
    request_id: str = "unknown",
) -> dict:
    """
    Calls the NVIDIA NIM API with retry logic.
    Returns {"content": str, "model": str, "latency": float} on success,
    or {"error": str} after all retries are exhausted.
    """

    for attempt in range(MAX_RETRIES + 1):
        start = time.time()

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    NIM_URL,
                    headers={
                        "Authorization": f"Bearer {NVIDIA_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model":       model,
                        "messages":    messages,
                        "temperature": 0.7,
                        "max_tokens":  max_tokens,
                    },
                )

            latency = round(time.time() - start, 2)

            if resp.status_code == 200:
                data = resp.json()
                content = _extract_content(data)

                if content:
                    logger.info(
                        f"[service] rid={request_id} model={model} latency={latency}s"
                    )
                    return {
                        "content": content,
                        "model":   model,
                        "latency": latency,
                    }

                # Bad format — retry rather than bail out of the whole chain
                logger.warning(
                    f"[service] rid={request_id} attempt={attempt} "
                    f"bad_format model={model} — retrying"
                )
                # fall through to sleep + next attempt

            else:
                logger.warning(
                    f"[service] rid={request_id} attempt={attempt} "
                    f"status={resp.status_code} model={model}"
                )

        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(
                f"[service] rid={request_id} attempt={attempt} "
                f"network_error={str(e)} model={model}"
            )

        await asyncio.sleep(0.5 * attempt)

    logger.error(
        f"[service] rid={request_id} max_retries_exceeded model={model}"
    )
    return {"error": "max_retries_exceeded"}


# ──────────────────────────────────────────────────────────────────────────────
# 3. FALLBACK ENGINE
# ──────────────────────────────────────────────────────────────────────────────

async def generate_response(message: str, request_id: str) -> dict:
    """
    Full AI pipeline:
    1. Route message to primary model
    2. Try primary model
    3. Walk fallback chain on failure
    """
    primary_model = await route_message(message, request_id)

    fallback_models = [primary_model] + [
        MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != primary_model
    ]

    for model in fallback_models:

        result = await call_nim(
            model=model,
            messages=[{"role": "user", "content": message}],
            request_id=request_id,
        )

        if "content" in result:
            content = result["content"]

            # Lightweight quality guard — skip suspiciously short replies
            if len(content.strip()) < 15:
                logger.warning(
                    f"[service] rid={request_id} low_quality model={model} → next"
                )
                continue

            return {
                "response":   content,
                "model_used": model,
                "latency":    result.get("latency", 0),
            }

        logger.warning(f"[service] rid={request_id} model_failed={model}")

    return {
        "response":   "⚠️ All AI models are currently unavailable.",
        "model_used": "none",
        "latency":    0,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 4. HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _extract_content(data: dict) -> str | None:
    """
    Normalizes NIM response shapes into a plain string.
    Handles both streaming (delta) and non-streaming (message) formats.
    """
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        pass

    try:
        return data["choices"][0]["delta"]["content"]
    except (KeyError, IndexError, TypeError):
        pass

    if isinstance(data.get("text"), str):
        return data["text"]

    return None