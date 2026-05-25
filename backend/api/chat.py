import asyncio
import json as _json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from config import MODEL_PRICING, MODELS
from core.db import get_db
from llm import retriever, service
from llm.embeddings import embed as embed_text
from llm.summarizer import compress_history, update_memory, update_project_summary
from models import Conversation, Message, User, UserMemory
from observability import events, metrics, observability
from observability.token_metrics import record_tokens
from observability.prom_metrics import (
    ERROR_COUNT, LATENCY, MODEL_LATENCY, MODEL_USAGE,
    REQUEST_COUNT, REQUEST_LATENCY,
)
from rate_limiter import limit

router = APIRouter(tags=["chat"])
logger = logging.getLogger("chat")


class ChatRequest(BaseModel):
    message:         str          = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None   = None
    model_override:  str | None   = None
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


async def _resolve_conversation(
    req: ChatRequest,
    current_user: User,
    db: AsyncSession,
) -> Conversation:
    if req.conversation_id:
        try:
            cid = uuid.UUID(req.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id")
        conv = await db.get(Conversation, cid)
        if not conv or conv.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv

    conv = Conversation(user_id=current_user.id, title=req.message[:60].strip())
    db.add(conv)
    await db.flush()
    return conv


async def _build_stream_context(
    req: ChatRequest,
    conv: Conversation,
    current_user: User,
    db: AsyncSession,
    rid: str,
) -> dict:
    memory_row     = await db.get(UserMemory, current_user.id)
    memory_enabled = conv.memory_enabled
    memory_sheet   = (memory_row.content         if memory_row and memory_row.content         else "") if memory_enabled else ""
    project_summary= (memory_row.project_summary if memory_row and memory_row.project_summary else "") if memory_enabled else ""

    is_ref    = retriever.is_reference_query(req.message)
    query_emb = None
    if req.conversation_id or is_ref:
        query_emb = await embed_text(req.message, input_type="query")

    history_summary = conv.history_summary or ""
    history: list[dict] = []
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

    top_k     = 8 if is_ref else 3
    retrieved: list[str] = []
    if query_emb:
        retrieved = await retriever.retrieve(db, query_emb, conv.id, top_k=top_k)
        if is_ref and not retrieved:
            retrieved = await retriever.retrieve_global(db, query_emb, conv.id, current_user.id)

    file_chunks: list[str] = []
    file_names:  list[str] = []
    file_ids:    list      = []
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
                logger.warning("[file_ctx] rid=%s file_ids=%d but NO chunks retrieved", rid, len(file_ids))

    return {
        "memory_enabled":  memory_enabled,
        "memory_sheet":    memory_sheet,
        "project_summary": project_summary,
        "history_summary": history_summary,
        "history":         history,
        "retrieved":       retrieved,
        "file_chunks":     file_chunks,
        "file_names":      file_names,
        "file_ids":        file_ids,
    }


def _extract_model_params(req: ChatRequest) -> dict | None:
    p: dict = {}
    if req.temperature is not None: p["temperature"] = req.temperature
    if req.max_tokens  is not None: p["max_tokens"]  = req.max_tokens
    if req.top_p       is not None: p["top_p"]       = req.top_p
    return p or None


@router.post("/chat")
async def chat(
    req:          ChatRequest,
    request:      Request,
    current_user: User = Depends(get_current_user),
    _:            None = limit(15, 60, "chat"),
):
    rid     = request.state.request_id
    t_start = metrics.record_request_start()
    status  = "success"
    error_type   = None
    model_used   = "unknown"
    cache_hit    = False
    fallback_used= False

    try:
        result = await service.generate_response(req.message, rid)
        model_used    = result.get("model", "unknown")
        cache_hit     = result.get("cache_hit", False)
        fallback_used = result.get("fallback_used", False)
        return {"success": True, "data": {"model": model_used, "response": result.get("response")}, "meta": {"request_id": rid}}

    except Exception:
        status     = "error"
        error_type = "unknown"
        await observability.publish_error_event(events.error_event(error_type="unknown", model=model_used))
        logger.exception("[chat] failed rid=%s", rid)
        return {"success": False, "error": {"type": "internal_error", "message": "Internal server error"}, "meta": {"request_id": rid}}

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
                events.request_event(request_id=rid, model=model_used, latency_ms=latency_ms,
                                     status=status, cache_hit=cache_hit, fallback_used=fallback_used)
            )
        except Exception:
            pass


@router.post("/chat/stream")
async def chat_stream(
    req:          ChatRequest,
    request:      Request,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
    _:            None         = limit(15, 60, "chat"),
):
    rid  = request.state.request_id
    logger.info("[chat/stream] rid=%s user=%s", rid, current_user.username)

    conv         = await _resolve_conversation(req, current_user, db)
    ctx          = await _build_stream_context(req, conv, current_user, db, rid)
    model_params = _extract_model_params(req)
    effective_model = _resolve_model(req.model_override) or _resolve_model(conv.locked_model)
    system_prompt   = conv.system_prompt or None

    if req.compare:
        await db.commit()
        common = service.build_context_messages(
            ctx["memory_sheet"], ctx["project_summary"], ctx["retrieved"],
            ctx["history_summary"], ctx["history"], ctx["memory_enabled"],
            system_prompt, ctx["file_chunks"], ctx["file_names"], ctx["file_ids"],
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
                req.message, ctx["history"], ctx["memory_sheet"], ctx["project_summary"],
                ctx["history_summary"], ctx["retrieved"], rid,
                memory_enabled=ctx["memory_enabled"], model_override=effective_model,
                model_params=model_params, system_prompt=system_prompt,
                file_chunks=ctx["file_chunks"], file_names=ctx["file_names"],
                file_ids=ctx["file_ids"], conv_id=conv.id,
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
                        pricing           = MODEL_PRICING.get(model_used, {})
                        prompt_tokens     = _estimate_tokens(
                            ctx["memory_sheet"], ctx["project_summary"],
                            ctx["history_summary"],
                            *[m["content"] for m in ctx["history"]],
                            req.message,
                        )
                        completion_tokens = len(full_response) // 4
                        total_tokens      = prompt_tokens + completion_tokens
                        cost_usd          = (
                            prompt_tokens     / 1_000_000 * pricing.get("input",  0.0) +
                            completion_tokens / 1_000_000 * pricing.get("output", 0.0)
                        )

                        asst_msg = Message(
                            conversation_id=conv.id, role="assistant",
                            content=full_response, model=model_used,
                            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                            total_tokens=total_tokens, cost_usd=cost_usd,
                        )
                        db.add(asst_msg)
                        await db.commit()
                        record_tokens(model_used, prompt_tokens, completion_tokens, cost_usd)
                        asyncio.create_task(_embed_exchange(asst_msg.id, conv.id, req.message, full_response))

                        cnt     = await db.execute(select(func.count()).select_from(Message).where(Message.conversation_id == conv.id))
                        all_count = cnt.scalar_one()
                        asst_cnt  = await db.execute(select(func.count()).select_from(Message).where(Message.conversation_id == conv.id, Message.role == "assistant"))
                        asst_count= asst_cnt.scalar_one()

                        ctx_tokens = _estimate_tokens(
                            ctx["memory_sheet"], ctx["project_summary"], ctx["history_summary"],
                            *[m["content"] for m in ctx["history"]], req.message, full_response,
                        )
                        if ctx_tokens > 4000 or (all_count > 10 and all_count % 15 == 0):
                            asyncio.create_task(compress_history(conv.id))
                            asyncio.create_task(update_project_summary(current_user.id))
                        if ctx_tokens > 3000 or asst_count % 10 == 0:
                            asyncio.create_task(update_memory(current_user.id, conv.id))

                        event["prompt_tokens"]     = prompt_tokens
                        event["completion_tokens"] = completion_tokens
                        event["total_tokens"]      = total_tokens
                        event["cost_usd"]          = round(cost_usd, 8)

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
