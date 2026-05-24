from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncio
import json as _json
import logging
import uuid
import httpx

from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from observability import metrics, events, observability
from llm import service
from core.redis_client import init_redis, get_redis
import llm.client as llm_client
from models import User, Conversation, Message
from auth import auth_router, get_current_user
from config import MODELS, REQUEST_TIMEOUT
from core.db import init_db, get_db
from rate_limiter import limit
from observability.metrics_api import router as metrics_router
from storage.storage_manager import StorageManager
from prometheus_fastapi_instrumentator import Instrumentator
from observability.prom_metrics import (
    export_metrics,
    CONTENT_TYPE_LATEST,
    REQUEST_COUNT,
    ERROR_COUNT,
    REQUEST_LATENCY,
    MODEL_USAGE,
    MODEL_LATENCY,
    LATENCY,
)

from api.files import router as files_router
from api.conversations import router as conversations_router
from core.logger import setup_logging
from llm.summarizer import get_memory, update_memory, compress_history

setup_logging()

storage = StorageManager()
logger  = logging.getLogger("router")


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("[startup] init db...")
    await init_db()

    logger.info("[startup] init redis (authoritative)...")

    try:
        init_redis()

        redis = get_redis()
        await redis.ping()

        logger.info("[startup] redis ready")

    except Exception as e:
        logger.error(f"[startup] redis failed to initialize: {e}")

    logger.info("[startup] init http client...")
    llm_client.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    logger.info("[startup] ready")

    yield

    logger.info("[shutdown] closing http client...")

    if llm_client.client:
        await llm_client.client.aclose()

    logger.info("[shutdown] complete")


app = FastAPI(
    title="NIM LLM Router",
    lifespan=lifespan,
)

app.include_router(files_router,         prefix="/files")
app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(conversations_router)

Instrumentator().instrument(app).expose(app, endpoint="/prometheus")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


class ChatRequest(BaseModel):
    message:         str      = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None


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


@app.post("/chat", response_model=SuccessResponse | ErrorResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    _: None = limit(15, 60, "chat"),
):

    rid = request.state.request_id

    logger.info(f"[chat] rid={rid} user={current_user.username}")

    t_start = metrics.record_request_start()

    status = "success"
    error_type = None
    model_used = "unknown"
    cache_hit = False
    fallback_used = False

    try:
        result = await service.generate_response(req.message, rid)

        model_used = result.get("model", "unknown")
        cache_hit = result.get("cache_hit", False)
        fallback_used = result.get("fallback_used", False)

        response_payload = SuccessResponse(
            data={
                "model": model_used,
                "response": result.get("response"),
            },
            meta=ResponseMeta(request_id=rid),
        )

    except httpx.TimeoutException:
        status = "error"
        error_type = "timeout"

        await observability.publish_error_event(
            events.error_event(error_type="timeout", model=model_used)
        )

        response_payload = ErrorResponse(
            error={"type": "timeout", "message": "Model timeout"},
            meta=ResponseMeta(request_id=rid),
        )

    except Exception:
        status = "error"
        error_type = "unknown"

        await observability.publish_error_event(
            events.error_event(error_type="unknown", model=model_used)
        )

        logger.exception(f"[chat] failed rid={rid}")

        response_payload = ErrorResponse(
            error={"type": "internal_error", "message": "Internal server error"},
            meta=ResponseMeta(request_id=rid),
        )

    finally:
        latency_ms = metrics.record_request_end(
            start=t_start,
            model=model_used,
            status=status,
            cache_hit=cache_hit,
            error_type=error_type,
            fallback_used=fallback_used,
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
                    request_id=rid,
                    model=model_used,
                    latency_ms=latency_ms,
                    status=status,
                    cache_hit=cache_hit,
                    fallback_used=fallback_used,
                )
            )
        except Exception:
            pass

        logger.info({
            "request_id": rid,
            "latency_ms": round(latency_ms, 2),
            "model": model_used,
            "status": status,
            "cache_hit": cache_hit,
            "fallback_used": fallback_used,
            "error_type": error_type,
        })

    return response_payload


@app.post("/chat/stream")
async def chat_stream(
    req:          ChatRequest,
    request:      Request,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
    _:            None         = limit(15, 60, "chat"),
):
    rid = request.state.request_id
    logger.info("[chat/stream] rid=%s user=%s", rid, current_user.username)

    # ── resolve or create conversation ────────────────────────────────────────
    if req.conversation_id:
        try:
            cid  = uuid.UUID(req.conversation_id)
            conv = await db.get(Conversation, cid)
            if not conv or conv.user_id != current_user.id:
                raise HTTPException(status_code=404, detail="Conversation not found")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id")
    else:
        conv = Conversation(
            user_id = current_user.id,
            title   = req.message[:60].strip(),
        )
        db.add(conv)
        await db.flush()

    # ── load last 10 raw messages + history summary ───────────────────────────
    hist_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(hist_result.scalars().all())]
    history_summary = conv.history_summary or ""

    # ── load memory sheet ─────────────────────────────────────────────────────
    memory_sheet = await get_memory(db, current_user.id)

    # ── save user message ─────────────────────────────────────────────────────
    db.add(Message(conversation_id=conv.id, role="user", content=req.message))
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()

    conv_id_str = str(conv.id)
    t_start     = metrics.record_request_start()

    async def event_generator():
        status        = "success"
        model_used    = "unknown"
        cache_hit     = False
        fallback_used = False
        accumulated   = []

        try:
            async for event in service.generate_stream(req.message, history, memory_sheet, history_summary, rid):
                if event["type"] == "token":
                    accumulated.append(event["content"])
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "done":
                    model_used    = event.get("model", "unknown")
                    cache_hit     = event.get("cache_hit", False)
                    fallback_used = event.get("fallback_used", False)
                    full_response = "".join(accumulated)

                    try:
                        db.add(Message(
                            conversation_id = conv.id,
                            role            = "assistant",
                            content         = full_response,
                            model           = model_used,
                        ))
                        await db.commit()

                        # count messages for background task triggers
                        cnt = await db.execute(
                            select(Message)
                            .where(Message.conversation_id == conv.id)
                        )
                        all_count = len(cnt.scalars().all())
                        asst_cnt = await db.execute(
                            select(Message)
                            .where(Message.conversation_id == conv.id, Message.role == "assistant")
                        )
                        asst_count = len(asst_cnt.scalars().all())

                        # compress old history every 5 total exchanges past 10
                        if all_count > 10 and all_count % 5 == 0:
                            asyncio.create_task(compress_history(conv.id))

                        # update memory sheet every 5 assistant messages
                        if asst_count % 5 == 0:
                            asyncio.create_task(update_memory(current_user.id, conv.id))

                    except Exception:
                        logger.exception("[chat/stream] db save failed rid=%s", rid)

                    event["conversation_id"] = conv_id_str
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "error":
                    status = "error"
                    yield f"data: {_json.dumps(event)}\n\n"

        except Exception:
            status = "error"
            logger.exception("[chat/stream] failed rid=%s", rid)
            yield f"data: {_json.dumps({'type': 'error', 'message': 'Internal server error'})}\n\n"

        finally:
            latency_ms = metrics.record_request_end(
                start=t_start, model=model_used, status=status,
                cache_hit=cache_hit, fallback_used=fallback_used,
            )
            REQUEST_LATENCY.observe(latency_ms / 1000)
            LATENCY.observe(latency_ms / 1000)
            REQUEST_COUNT.labels(status=status).inc()
            if status == "success" and model_used != "unknown":
                MODEL_USAGE.labels(model=model_used).inc()
                MODEL_LATENCY.labels(model=model_used).observe(latency_ms / 1000)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/metrics")
def metrics_endpoint():
    try:
        return Response(
            content=export_metrics(),
            media_type=CONTENT_TYPE_LATEST,
        )

    except Exception:
        logger.exception("[metrics] export failed")

        return Response(
            content="# metrics export failed\n",
            media_type="text/plain",
            status_code=200,
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"[global_error] {request.url.path}")

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "type": "internal_error",
                "message": "Internal server error",
            },
            "meta": {
                "request_id": getattr(request.state, "request_id", "unknown")
            },
        },
    )


@app.get("/health")
def health():
    return SuccessResponse(
        data={
            "status": "ok",
            "models": list(MODELS.keys()),
        },
        meta=ResponseMeta(request_id="health"),
    )
