import asyncio
import json as _json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from cache import get_cached_response
from core.db import get_db
from llm import service
from models import Conversation, ConversationFile, Message, User, Workspace
from observability import events, metrics, observability
from observability.prom_metrics import (
    ERROR_COUNT, LATENCY, MODEL_LATENCY, MODEL_USAGE,
    REQUEST_COUNT, REQUEST_LATENCY,
)
from observability.token_metrics import record_tokens
from rate_limiter import limit, check_model_rate

from .helpers import (
    _build_stream_context, _check_cost_cap, _extract_model_params,
    _resolve_conversation, _resolve_model,
)
from .background import (
    _auto_title, _calculate_tokens_and_cost, _embed_exchange, _estimate_tokens, _generate_proactive,
)
from .schemas import ChatRequest

router = APIRouter()
logger = logging.getLogger("chat")


@router.post("/chat/stream")
async def chat_stream(
    req:          ChatRequest,
    request:      Request,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
    _:            None         = limit(15, 60, "chat"),
):
    rid = request.state.request_id
    logger.info("[chat/stream] rid=%s user=%s", rid, current_user.username)

    await _check_cost_cap(current_user, db)

    conv            = await _resolve_conversation(req, current_user, db)
    model_params    = _extract_model_params(req)
    effective_model = _resolve_model(req.model_override) or _resolve_model(conv.locked_model)
    if effective_model:
        await check_model_rate(effective_model, current_user.username)

    # Early cache check — skip expensive context building on hit
    if not req.image_b64 and not model_params:
        has_files = False
        if conv.id:
            cnt = await db.execute(
                select(func.count()).select_from(ConversationFile)
                .where(ConversationFile.conversation_id == conv.id)
            )
            has_files = cnt.scalar_one() > 0
        if not has_files:
            history_tail = ""
            if conv.id:
                rows = await db.execute(
                    select(Message.content)
                    .where(Message.conversation_id == conv.id)
                    .order_by(Message.created_at.desc())
                    .limit(4)
                )
                history_tail = "\n".join(reversed(rows.scalars().all()))
            cache_model = effective_model or ""
            sys_prompt = conv.system_prompt or ""
            if conv.workspace_id:
                ws = await db.get(Workspace, conv.workspace_id)
                ws_sp = ws.system_prompt if ws else None
                if ws_sp and sys_prompt:
                    sys_prompt = ws_sp + "\n\n" + sys_prompt
                elif ws_sp:
                    sys_prompt = ws_sp
            cached = await get_cached_response(
                req.message, model=cache_model,
                history_tail=history_tail, system_prompt=sys_prompt,
            )
            if cached:
                t_start = metrics.record_request_start()
                conv_id_str = str(conv.id)
                user_msg = Message(conversation_id=conv.id, role="user", content=req.message)
                db.add(user_msg)
                conv.updated_at = datetime.now(timezone.utc)
                await db.flush()

                async def cached_generator():
                    resp = cached["response"]
                    model_used = cached.get("model", "cache")
                    yield f"data: {_json.dumps({'type': 'token', 'content': resp})}\n\n"
                    asst_msg = Message(
                        conversation_id=conv.id, role="assistant",
                        content=resp, model=model_used,
                    )
                    db.add(asst_msg)
                    await db.commit()
                    cnt = await db.execute(select(func.count()).select_from(Message).where(Message.conversation_id == conv.id))
                    if cnt.scalar_one() == 2:
                        asyncio.create_task(_auto_title(conv.id, req.message, resp))
                    done = {
                        "type": "done", "model": model_used, "cache_hit": True,
                        "fallback_used": False, "conversation_id": conv_id_str, "provenance": [],
                    }
                    yield f"data: {_json.dumps(done)}\n\n"
                    latency_ms = metrics.record_request_end(
                        start=t_start, model=model_used, status="success", cache_hit=True,
                    )
                    REQUEST_LATENCY.observe(latency_ms / 1000)
                    LATENCY.observe(latency_ms / 1000)
                    REQUEST_COUNT.labels(status="success").inc()

                return StreamingResponse(
                    cached_generator(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

    ctx = await _build_stream_context(req, conv, current_user, db, rid)
    # Workspace system_prompt takes precedence; merge with conv system_prompt if both set
    ws_sysprompt  = ctx.get("workspace_sysprompt")
    conv_sysprompt = conv.system_prompt or None
    if ws_sysprompt and conv_sysprompt:
        system_prompt = ws_sysprompt + "\n\n" + conv_sysprompt
    else:
        system_prompt = ws_sysprompt or conv_sysprompt

    if req.compare:
        await db.commit()
        common  = service.build_context_messages(
            ctx["memory_sheet"], ctx["project_summary"], ctx["retrieved"],
            ctx["history_summary"], ctx["history"], ctx["memory_enabled"],
            system_prompt, ctx["file_chunks"], ctx["file_names"], ctx["file_ids"],
            workspace_memory=ctx.get("workspace_memory", ""),
            graph_context=ctx.get("graph_context", ""),
            graph_facts=ctx.get("graph_facts", ""),
            conflicted_facts=ctx.get("conflicted_facts", frozenset()),
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
    await db.flush()
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
                image_b64=req.image_b64, image_mime_type=req.image_mime_type,
                workspace_memory=ctx.get("workspace_memory", ""),
                graph_context=ctx.get("graph_context", ""),
                graph_facts=ctx.get("graph_facts", ""),
                conflicted_facts=ctx.get("conflicted_facts", frozenset()),
                fact_saliences=ctx.get("fact_saliences", {}),
            ):
                if event["type"] == "token":
                    accumulated.append(event["content"])
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] in ("tool_call", "tool_result", "ask_user", "confirm_write_memory"):
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "done":
                    model_used    = event.get("model", "unknown")
                    cache_hit     = event.get("cache_hit", False)
                    fallback_used = event.get("fallback_used", False)
                    full_response = "".join(accumulated)

                    try:
                        pt, ct, tt, cost = _calculate_tokens_and_cost(event, ctx, req, full_response, model_used)

                        asst_msg = Message(
                            conversation_id=conv.id, role="assistant",
                            content=full_response, model=model_used,
                            prompt_tokens=pt, completion_tokens=ct,
                            total_tokens=tt, cost_usd=cost,
                        )
                        db.add(asst_msg)
                        await db.commit()
                        record_tokens(model_used, pt, ct, cost)
                        asyncio.create_task(_embed_exchange(asst_msg.id, conv.id, req.message, full_response))
                        if ctx.get("memory_enabled"):
                            from llm.graph_memory import extract_and_store as _graph_extract
                            asyncio.create_task(_graph_extract(current_user.id, req.message, full_response))

                        cnt       = await db.execute(select(func.count()).select_from(Message).where(Message.conversation_id == conv.id))
                        all_count = cnt.scalar_one()
                        asst_cnt  = await db.execute(select(func.count()).select_from(Message).where(Message.conversation_id == conv.id, Message.role == "assistant"))

                        if all_count == 2:
                            asyncio.create_task(_auto_title(conv.id, req.message, full_response))
                        asst_count = asst_cnt.scalar_one()

                        ctx_tokens = _estimate_tokens(
                            ctx["memory_sheet"], ctx["project_summary"], ctx["history_summary"],
                            *[m["content"] for m in ctx["history"]], req.message, full_response,
                        )
                        if ctx_tokens > 4000 or (all_count > 10 and all_count % 15 == 0):
                            asyncio.create_task(compress_history(conv.id))
                            asyncio.create_task(update_project_summary(current_user.id))
                        if ctx_tokens > 3000 or asst_count % 10 == 0:
                            asyncio.create_task(update_memory(current_user.id, conv.id))

                        # Enqueue background insight every 10 assistant messages
                        if asst_count % 10 == 0:
                            from core.arq_pool import get_arq_pool
                            pool = get_arq_pool()
                            if pool:
                                await pool.enqueue_job("generate_insight_job", current_user.id)

                        event["prompt_tokens"]     = pt
                        event["completion_tokens"] = ct
                        event["total_tokens"]      = tt
                        event["cost_usd"]          = round(cost, 8)

                    except Exception:
                        logger.exception("[chat/stream] db save failed rid=%s", rid)
                        await db.rollback()

                    # Proactive suggestion before closing stream
                    try:
                        suggestion = await _generate_proactive(req.message, full_response)
                        if suggestion:
                            yield f"data: {_json.dumps({'type': 'proactive', 'content': suggestion})}\n\n"
                    except Exception:
                        pass

                    seen: set = set()
                    provenance = []
                    for hit in ctx.get("retrieved", []) + ctx.get("file_chunks", []):
                        cid = str(hit.get("chunk_id", ""))
                        if not cid or cid in seen:
                            continue
                        seen.add(cid)
                        provenance.append({
                            "chunk_id":       cid,
                            "source_id":      str(hit["source_id"]) if hit.get("source_id") is not None else None,
                            "dense_score":    hit.get("dense_score", 0.0),
                            "sparse_score":   hit.get("sparse_score", 0.0),
                            "final_score":    hit.get("final_score", 0.0),
                            "retrieval_type": hit.get("retrieval_type", ""),
                        })
                    event["provenance"] = provenance

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
