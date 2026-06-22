import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from core.db import get_db
from llm import service
from models import User
from observability import events, metrics, observability
from observability.prom_metrics import (
    ERROR_COUNT, LATENCY, MODEL_LATENCY, MODEL_USAGE,
    REQUEST_COUNT, REQUEST_LATENCY,
)
from rate_limiter import limit

from .helpers import _check_cost_cap
from .schemas import ChatRequest

router = APIRouter(tags=["chat"])
logger = logging.getLogger("chat")


@router.post("/chat")
async def chat(
    req:          ChatRequest,
    request:      Request,
    current_user: User = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
    _:            None = limit(15, 60, "chat"),
):
    rid          = request.state.request_id
    # Cost cap applies here too — otherwise a capped user could bypass the limit
    # via the stateless /chat path. Checked BEFORE the try below so the 402
    # HTTPException isn't swallowed by the generic error handler.
    await _check_cost_cap(current_user, db)
    t_start      = metrics.record_request_start()
    status       = "success"
    error_type   = None
    model_used   = "unknown"
    cache_hit    = False
    fallback_used= False

    try:
        result = await service.generate_response(req.message, rid)
        model_used    = result.get("model", "unknown")
        cache_hit     = result.get("cache_hit", False)
        fallback_used = result.get("fallback_used", False)
        return {
            "success": True,
            "data":    {"model": model_used, "response": result.get("response")},
            "meta":    {"request_id": rid},
        }

    except Exception:
        status     = "error"
        error_type = "unknown"
        await observability.publish_error_event(events.error_event(error_type="unknown", model=model_used))
        logger.exception("[chat] failed rid=%s", rid)
        return {
            "success": False,
            "error":   {"type": "internal_error", "message": "Internal server error"},
            "meta":    {"request_id": rid},
        }

    finally:
        latency_ms = metrics.record_request_end(
            start=t_start, model=model_used, status=status,
            cache_hit=cache_hit, error_type=error_type, fallback_used=fallback_used,
        )
        REQUEST_LATENCY.observe(latency_ms / 1000)
        LATENCY.observe(latency_ms / 1000)
        REQUEST_COUNT.labels(status=status).inc()
        if status == "success" and model_used != "unknown":
            MODEL_USAGE.labels(model=model_used).inc()
            MODEL_LATENCY.labels(model=model_used).observe(latency_ms / 1000)
        if status == "error":
            ERROR_COUNT.labels(type=error_type or "unknown").inc()
        try:
            await observability.publish_request_event(
                events.request_event(
                    request_id=rid, model=model_used, latency_ms=latency_ms,
                    status=status, cache_hit=cache_hit, fallback_used=fallback_used,
                )
            )
        except Exception:
            pass
