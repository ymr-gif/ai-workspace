import asyncio
import logging
import time

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

import llm.client as llm_client
from config import MODELS, MODEL_EMBEDDING, NVIDIA_API_KEY, NIM_URL, NIM_EMBEDDING_URL
from core.redis_client import get_redis
from observability.prom_metrics import CONTENT_TYPE_LATEST, export_metrics

router = APIRouter(tags=["system"])
logger = logging.getLogger("system")

_PING_TIMEOUT = 5  # seconds per check


class ResponseMeta(BaseModel):
    request_id: str


class SuccessResponse(BaseModel):
    success: bool = True
    data: dict
    meta: ResponseMeta


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict
    meta: ResponseMeta


async def _ping_nim() -> dict:
    t = time.monotonic()
    try:
        resp = await llm_client.client.post(
            NIM_URL,
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODELS["llama"], "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=_PING_TIMEOUT,
        )
        latency = int((time.monotonic() - t) * 1000)
        if resp.status_code == 200:
            return {"status": "ok", "latency_ms": latency}
        return {"status": "error", "detail": f"http_{resp.status_code}", "latency_ms": latency}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


async def _ping_embedding() -> dict:
    t = time.monotonic()
    try:
        resp = await llm_client.client.post(
            NIM_EMBEDDING_URL,
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL_EMBEDDING, "input": ["ping"], "input_type": "passage", "encoding_format": "float"},
            timeout=_PING_TIMEOUT,
        )
        latency = int((time.monotonic() - t) * 1000)
        if resp.status_code == 200:
            return {"status": "ok", "latency_ms": latency}
        return {"status": "error", "detail": f"http_{resp.status_code}", "latency_ms": latency}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


async def _ping_redis() -> dict:
    t = time.monotonic()
    try:
        r = get_redis()
        await asyncio.wait_for(r.ping(), timeout=3)
        latency = int((time.monotonic() - t) * 1000)
        return {"status": "ok", "latency_ms": latency}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


@router.get("/health")
async def health():
    nim, emb, redis = await asyncio.gather(
        _ping_nim(),
        _ping_embedding(),
        _ping_redis(),
        return_exceptions=False,
    )

    checks = {"nim": nim, "embedding": emb, "redis": redis}
    all_ok = all(c["status"] == "ok" for c in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "models": list(MODELS.keys()),
        "checks": checks,
    }


@router.get("/metrics")
def metrics_endpoint():
    try:
        return Response(content=export_metrics(), media_type=CONTENT_TYPE_LATEST)
    except Exception:
        logger.exception("[metrics] export failed")
        return Response(content="# metrics export failed\n", media_type="text/plain", status_code=200)
