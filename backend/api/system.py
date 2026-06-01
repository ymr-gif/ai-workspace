import asyncio
import logging
import platform
import socket
import time
from functools import lru_cache

import psutil

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

import llm.client as llm_client
from config import MODELS, MODEL_EMBEDDING, NVIDIA_API_KEY, NIM_URL, NIM_EMBEDDING_URL
from llm.circuit_breaker import record_failure, _THRESHOLD
from core.db import AsyncSessionLocal
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


async def _ping_db() -> dict:
    t = time.monotonic()
    try:
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2)
        latency = int((time.monotonic() - t) * 1000)
        return {"status": "ok", "latency_ms": latency}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


async def probe_models_on_startup() -> None:
    async def _probe(role: str, model_id: str) -> None:
        try:
            resp = await llm_client.client.post(
                NIM_URL,
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
                json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=_PING_TIMEOUT,
            )
            if resp.status_code == 200:
                logger.info("[probe] model=%s ok", role)
                return
            logger.warning("[probe] model=%s status=%s — pre-tripping circuit", role, resp.status_code)
        except Exception as e:
            logger.warning("[probe] model=%s error=%s — pre-tripping circuit", role, str(e)[:80])
        for _ in range(_THRESHOLD):
            await record_failure(model_id)

    await asyncio.gather(*(_probe(role, model_id) for role, model_id in MODELS.items()))


@router.get("/health")
async def health():
    nim, emb, redis, db = await asyncio.gather(
        _ping_nim(),
        _ping_embedding(),
        _ping_redis(),
        _ping_db(),
        return_exceptions=False,
    )

    checks = {"nim": nim, "embedding": emb, "redis": redis, "db": db}
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


# ── /hardware ──────────────────────────────────────────────────────────────────

def _gb(b: int) -> float:
    return round(b / (1024**3), 2)





@lru_cache(maxsize=1)
def _gpu_init():
    import pynvml
    pynvml.nvmlInit()
    return pynvml


def _get_gpu_info() -> dict | None:
    try:
        pynvml = _gpu_init()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return {
            "name": pynvml.nvmlDeviceGetName(handle).decode(),
            "vram_total_gb": _gb(mem.total),
            "vram_used_gb": _gb(mem.used),
            "temp_c": int(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)),
            "load_pct": float(pynvml.nvmlDeviceGetUtilizationRates(handle).gpu),
        }
    except Exception:
        return None


def _get_uptime() -> str:
    delta = time.time() - psutil.boot_time()
    days, rem = divmod(int(delta), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    return f"{days}d {hours}h {minutes}m"


@router.get("/system/hardware")
@router.get("/hardware")
async def hardware():
    freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_pct = await asyncio.to_thread(psutil.cpu_percent, interval=0.1)

    return {
        "cpu": {
            "name": platform.processor() or "Unknown",
            "freq_ghz": round(freq.current / 1000, 2) if freq else 0.0,
            "cores": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True),
            "usage_pct": cpu_pct,
        },
        "ram": {
            "total_gb": _gb(mem.total),
            "used_gb": _gb(mem.used),
            "available_gb": _gb(mem.available),
        },
        "gpu": _get_gpu_info(),
        "disk": {
            "total_gb": _gb(disk.total),
            "free_gb": _gb(disk.free),
        },
        "uptime": _get_uptime(),
        "hostname": socket.gethostname(),
    }
