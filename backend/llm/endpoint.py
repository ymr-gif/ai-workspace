"""Health-gated chat-endpoint selection (primary → NIM fallback).

Picks the chat-completions base URL per request: the preferred `LLM_PRIMARY_URL`
(e.g. a homelab llama.cpp over WireGuard) when it probes healthy, else `NIM_URL`.
The verdict is cached (Redis when USE_REDIS, else in-process) for `LLM_HEALTH_TTL`
seconds so we don't probe on every call. A connection-level failure to the primary
mid-request marks it unhealthy immediately, so the next attempt/request re-picks NIM.

Disabled by default (`LLM_FAILOVER_ENABLED=false`) → `pick_chat_url()` returns
`config.NIM_URL` with no Redis touch and no probe, i.e. behaviour identical to before.

CHAT ONLY. There is deliberately no embedding equivalent: failing an embedding call
over to a different embedder mixes vector spaces and silently corrupts retrieval.
An embedder swap is a re-embed, not a failover.

All config is read as `config.X` at call time (never `from config import`) so
`/admin/env/reload` reaches the values live — same invariant as LLM_BACKEND.
"""
import time
import logging

import config
import llm.client as llm_client

logger = logging.getLogger("endpoint")

_HEALTH_KEY = "llm:primary_healthy"

# In-process cache used when USE_REDIS is off (single-process dev / tests).
# {"until": monotonic_deadline, "ok": bool} — empty dict = no cached verdict.
_local: dict = {}


def _probe_url(chat_url: str) -> str:
    """Derive the `/models` health URL from a chat-completions URL.

    http://host:8080/v1/chat/completions -> http://host:8080/v1/models
    Anything else -> append /models (best effort).
    """
    if chat_url.endswith("/chat/completions"):
        return chat_url[: -len("/chat/completions")] + "/models"
    return chat_url.rstrip("/") + "/models"


async def _get_cached() -> bool | None:
    """Return the cached health verdict, or None if absent/expired."""
    if config.USE_REDIS:
        try:
            from core.redis_client import get_redis
            val = await get_redis().get(_HEALTH_KEY)
            if val is None:
                return None
            return val in (b"1", "1")
        except Exception:
            return None
    entry = _local
    if entry and entry.get("until", 0) > time.monotonic():
        return entry.get("ok")
    return None


async def _set_cached(ok: bool) -> None:
    ttl = max(1, config.LLM_HEALTH_TTL)
    if config.USE_REDIS:
        try:
            from core.redis_client import get_redis
            await get_redis().set(_HEALTH_KEY, "1" if ok else "0", ex=ttl)
            return
        except Exception:
            pass  # fall through to local cache so we still throttle probes
    _local["until"] = time.monotonic() + ttl
    _local["ok"] = ok


async def _probe(chat_url: str) -> bool:
    """GET the primary's /models with a short timeout. True iff HTTP 200."""
    if llm_client.client is None:
        return False
    url = _probe_url(chat_url)
    try:
        resp = await llm_client.client.get(url, timeout=config.LLM_HEALTH_TIMEOUT)
        healthy = resp.status_code == 200
        if not healthy:
            logger.warning("[endpoint] primary probe non-200 url=%s status=%s", url, resp.status_code)
        return healthy
    except Exception as e:
        logger.warning("[endpoint] primary probe failed url=%s err=%s", url, e)
        return False


async def pick_chat_url() -> str:
    """Choose the chat-completions URL for this call.

    Returns config.NIM_URL unchanged when failover is off or no primary is set.
    """
    if not config.LLM_FAILOVER_ENABLED or not config.LLM_PRIMARY_URL:
        return config.NIM_URL

    healthy = await _get_cached()
    if healthy is None:
        healthy = await _probe(config.LLM_PRIMARY_URL)
        await _set_cached(healthy)

    if healthy:
        return config.LLM_PRIMARY_URL
    return config.NIM_URL


async def mark_primary_unhealthy() -> None:
    """Force NIM for the next `LLM_HEALTH_TTL` seconds.

    Called when a request to the primary fails at the connection level, so a
    mid-request outage fails over on the very next attempt without re-probing.
    No-op when failover is disabled.
    """
    if not config.LLM_FAILOVER_ENABLED or not config.LLM_PRIMARY_URL:
        return
    await _set_cached(False)
    logger.info("[endpoint] primary marked unhealthy for %ds", max(1, config.LLM_HEALTH_TTL))


def is_primary(url: str) -> bool:
    """True iff `url` is the configured primary (used to decide whether a failure
    should mark the primary unhealthy — a NIM failure must not)."""
    return bool(config.LLM_PRIMARY_URL) and url == config.LLM_PRIMARY_URL
