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
from sqlalchemy import func, select

from observability import metrics, events, observability
from llm import service
from core.redis_client import init_redis, get_redis
import llm.client as llm_client
from models import User, Conversation, Message, UserMemory
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
from api.memory import router as memory_router
from core.logger import setup_logging
from llm.summarizer import get_memory, update_memory, compress_history, update_project_summary
from llm.embeddings import embed as embed_text
from llm import retriever

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
app.include_router(memory_router)

Instrumentator().instrument(app).expose(app, endpoint="/prometheus")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


class ChatRequest(BaseModel):
    message:         str         = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None  = None
    model_override:  str | None  = None
    temperature:     float | None = Field(None, ge=0.0, le=2.0)
    max_tokens:      int | None   = Field(None, ge=1, le=4096)
    top_p:           float | None = Field(None, ge=0.0, le=1.0)
    compare:         bool         = False


def _resolve_model(name: str | None) -> str | None:
    if not name:
        return None
    if name in MODELS:
        return MODELS[name]
    if name in MODELS.values():
        return name
    return None


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


def _estimate_tokens(*texts: str) -> int:
    return sum(len(t) // 4 for t in texts if t)


async def _embed_exchange(
    message_id:      uuid.UUID,
    conversation_id: uuid.UUID,
    user_text:       str,
    assistant_text:  str,
) -> None:
    try:
        exchange = f"{user_text[:300]}\n{assistant_text[:400]}"
        emb = await embed_text(exchange, input_type="passage")
        if emb:
            await retriever.store_exchange(message_id, conversation_id, user_text, assistant_text, emb)
    except Exception:
        logger.exception("[embed_exchange] failed msg=%s", message_id)


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

    # ── load memory + project summary (one query) ────────────────────────────
    memory_row      = await db.get(UserMemory, current_user.id)
    memory_enabled  = conv.memory_enabled
    memory_sheet    = (memory_row.content         if memory_row and memory_row.content         else "") if memory_enabled else ""
    project_summary = (memory_row.project_summary if memory_row and memory_row.project_summary else "") if memory_enabled else ""

    # ── per-request model params + override ──────────────────────────────────
    model_params: dict | None = None
    _p: dict = {}
    if req.temperature is not None: _p["temperature"] = req.temperature
    if req.max_tokens  is not None: _p["max_tokens"]  = req.max_tokens
    if req.top_p       is not None: _p["top_p"]       = req.top_p
    if _p: model_params = _p

    # priority: per-request override > conversation lock
    effective_model = _resolve_model(req.model_override) or _resolve_model(conv.locked_model)
    system_prompt   = conv.system_prompt or None

    # ── embed query once (reused for weighting + retrieval) ───────────────────
    is_ref    = retriever.is_reference_query(req.message)
    query_emb = None
    if req.conversation_id or is_ref:
        query_emb = await embed_text(req.message, input_type="query")

    # ── importance-weighted history: load 30, score, keep top 10 ─────────────
    history_summary = conv.history_summary or ""
    if req.conversation_id:
        cand_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(30)
        )
        candidates = list(reversed(cand_result.scalars().all()))

        relevance_map = {}
        if query_emb:
            relevance_map = await retriever.get_relevance_scores(db, conv.id, query_emb)

        n = len(candidates)
        scored = []
        for i, m in enumerate(candidates):
            recency   = i / max(n - 1, 1)
            relevance = relevance_map.get(m.id, 0.0)
            scored.append((0.6 * recency + 0.4 * relevance, i, m))

        scored.sort(key=lambda x: -x[0])
        top_msgs = [m for _, _, m in scored[:10]]
        top_msgs.sort(key=lambda m: m.created_at)
        history = [{"role": m.role, "content": m.content} for m in top_msgs]
    else:
        history = []

    # ── on-demand rehydration: detect reference queries ────────────────────────
    top_k     = 8 if is_ref else 3
    retrieved = []
    if query_emb:
        retrieved = await retriever.retrieve(db, query_emb, conv.id, top_k=top_k)
        if is_ref and not retrieved:
            retrieved = await retriever.retrieve_global(
                db, query_emb, conv.id, current_user.id
            )

    # ── file-grounded context ─────────────────────────────────────────────────
    file_chunks: list[str]  = []
    file_names:  list[str]  = []
    file_ids:    list       = []
    if req.conversation_id:
        file_ids, file_names = await retriever.get_conversation_files(db, conv.id)
        if file_ids:
            if query_emb:
                file_chunks = await retriever.retrieve_from_files(db, query_emb, file_ids, top_k=5)
            else:
                file_chunks = await retriever.retrieve_files_sequential(db, file_ids, top_k=10)

            if file_chunks:
                for i, chunk in enumerate(file_chunks):
                    logger.info("[file_ctx] rid=%s chunk=%d/%d preview=%s",
                                rid, i + 1, len(file_chunks), repr(chunk[:120]))
            else:
                logger.warning("[file_ctx] rid=%s file_ids=%d but NO chunks retrieved — "
                               "files may still be processing or have no embeddings", rid, len(file_ids))

    # ── compare mode: run all models concurrently, skip DB save ─────────────
    if req.compare:
        await db.commit()  # persist new conversation if one was created
        common = service.build_context_messages(
            memory_sheet, project_summary, retrieved, history_summary,
            history, memory_enabled, system_prompt, file_chunks, file_names, file_ids,
        )
        t_cmp = metrics.record_request_start()

        async def compare_generator():
            try:
                async for event in service.compare_streams(req.message, common, model_params, rid):
                    if event.get("type") == "done":
                        event["conversation_id"] = str(conv.id)
                    yield f"data: {_json.dumps(event)}\n\n"
            except Exception:
                logger.exception("[chat/stream] compare failed rid=%s", rid)
                yield f"data: {_json.dumps({'type': 'error', 'message': 'Compare failed'})}\n\n"
            finally:
                metrics.record_request_end(start=t_cmp, model="compare", status="success")

        return StreamingResponse(
            compare_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── save user message ─────────────────────────────────────────────────────
    user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
    db.add(user_msg)
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    user_msg_id = user_msg.id

    conv_id_str = str(conv.id)
    t_start     = metrics.record_request_start()

    async def event_generator():
        status        = "success"
        model_used    = "unknown"
        cache_hit     = False
        fallback_used = False
        accumulated   = []

        try:
            async for event in service.generate_stream(
                req.message, history, memory_sheet, project_summary, history_summary, retrieved, rid,
                memory_enabled=memory_enabled, model_override=effective_model,
                model_params=model_params, system_prompt=system_prompt,
                file_chunks=file_chunks, file_names=file_names,
                file_ids=file_ids, conv_id=conv.id,
                user_id=current_user.id, db=db,
            ):
                if event["type"] == "token":
                    accumulated.append(event["content"])
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] in ("tool_call", "tool_result"):
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "done":
                    model_used    = event.get("model", "unknown")
                    cache_hit     = event.get("cache_hit", False)
                    fallback_used = event.get("fallback_used", False)
                    full_response = "".join(accumulated)

                    try:
                        asst_msg = Message(
                            conversation_id = conv.id,
                            role            = "assistant",
                            content         = full_response,
                            model           = model_used,
                        )
                        db.add(asst_msg)
                        await db.commit()
                        asst_msg_id = asst_msg.id

                        # embed exchange in background
                        asyncio.create_task(_embed_exchange(
                            asst_msg_id, conv.id, req.message, full_response
                        ))

                        # message counts for fallback triggers
                        cnt = await db.execute(
                            select(func.count()).select_from(Message)
                            .where(Message.conversation_id == conv.id)
                        )
                        all_count = cnt.scalar_one()
                        asst_cnt = await db.execute(
                            select(func.count()).select_from(Message)
                            .where(Message.conversation_id == conv.id, Message.role == "assistant")
                        )
                        asst_count = asst_cnt.scalar_one()

                        # context-pressure trigger (rough token estimate)
                        ctx_tokens = _estimate_tokens(
                            memory_sheet, project_summary, history_summary,
                            *[m["content"] for m in history],
                            req.message, full_response,
                        )

                        # compress + project summary: pressure > 4000t OR every 15 exchanges fallback
                        if ctx_tokens > 4000 or (all_count > 10 and all_count % 15 == 0):
                            asyncio.create_task(compress_history(conv.id))
                            asyncio.create_task(update_project_summary(current_user.id))

                        # update memory: pressure > 3000t OR every 10 assistant messages fallback
                        if ctx_tokens > 3000 or asst_count % 10 == 0:
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
