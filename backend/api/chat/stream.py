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
from models import Conversation, ConversationFile, Message, User
from observability import events, metrics, observability
from observability.prom_metrics import (
    ALL_MODELS_FAILED, ERROR_COUNT, LATENCY, MODEL_LATENCY, MODEL_USAGE,
    REQUEST_COUNT, REQUEST_LATENCY, STREAM_INTERRUPTIONS,
)
from observability.token_metrics import record_tokens
from rate_limiter import limit, check_model_rate

from llm.service.content_filter import compress_tool_dumps
from llm.summarizer.history import compress_history
from llm.summarizer.memory import update_memory
from llm.summarizer.project import update_project_summary

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


def _compute_grounding(provenance: list[dict], top_k: int) -> dict:
    """Grounding confidence from retrieval (Dim 3).

    Uses dense_score (cosine similarity, 0–1, fusion-mode-independent) — NOT
    final_score, which is not comparable across weighted vs RRF fusion. Combines
    top-chunk similarity with coverage (how full the result set is).
    """
    if not provenance:
        return {"level": "none", "score": None, "sources": []}
    top = sorted(provenance, key=lambda p: p.get("dense_score", 0.0), reverse=True)[:max(top_k, 1)]
    avg_dense = sum(p.get("dense_score", 0.0) for p in top) / len(top)
    coverage  = min(len(provenance) / max(top_k, 1), 1.0)
    score     = round(100 * (0.7 * avg_dense + 0.3 * coverage))
    level     = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return {
        "level": level,
        "score": score,
        "sources": [
            {
                "source_id":      p.get("source_id"),
                "dense_score":    round(p.get("dense_score", 0.0), 3),
                "retrieval_type": p.get("retrieval_type", ""),
            }
            for p in top
        ],
    }


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

    conv, rotation_info = await _resolve_conversation(req, current_user, db)
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
    last_session = ctx.get("last_session", "")

    system_prompt = conv.system_prompt or None

    if req.compare:
        await db.commit()
        common  = service.build_context_messages(
            ctx["memory_sheet"], ctx["project_summary"], ctx["retrieved"],
            ctx["history_summary"], ctx["history"],
            system_prompt, ctx["file_chunks"], ctx["file_names"], ctx["file_ids"],
            graph_context=ctx.get("graph_context", ""),
            graph_facts=ctx.get("graph_facts", ""),
            active_goals=ctx.get("active_goals", ""),
            conflicted_facts=ctx.get("conflicted_facts", frozenset()),
            last_session=last_session,
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
        status         = "success"
        model_used     = "unknown"
        cache_hit      = False
        fallback_used  = False
        accumulated    = []
        pending_question = ""
        tools_in_turn  = []
        turn_recorded  = False
        # Behind-the-scenes trace: seed with the context-build stages
        # (_build_stream_context), then append live status events from the
        # service layer. Persisted on the assistant message (done + abort).
        activity       = list(ctx.get("activity", []))

        async def _persist_abort(reason: str):
            # D/J2: a tool-loop/stream abort otherwise rolls back the whole
            # turn — the user message (flushed, not committed) and any partial
            # text vanish from history. Persist the user msg + a short assistant
            # note so failed turns stay visible. Commits the pending user_msg too.
            nonlocal turn_recorded
            if turn_recorded:
                return
            try:
                note = "".join(accumulated).strip() or f"⚠️ Turn aborted: {reason}"
                db.add(Message(
                    conversation_id=conv.id, role="assistant", content=note,
                    model=model_used if model_used != "unknown" else None,
                    activity_trace=activity or None,
                ))
                await db.commit()
                turn_recorded = True
            except Exception:
                await db.rollback()
                logger.warning("[chat/stream] abort-persist failed rid=%s", rid)

        # Emit rotation event if conversation was just archived
        if rotation_info:
            yield f"data: {_json.dumps({'type': 'rotated', **rotation_info})}\n\n"

        # Emit the context-build burst as ordered status events before the stream.
        for _st in activity:
            yield f"data: {_json.dumps({'type': 'status', **_st})}\n\n"

        try:
            async for event in service.generate_stream(
                req.message, ctx["history"], ctx["memory_sheet"], ctx["project_summary"],
                ctx["history_summary"], ctx["retrieved"], rid,
                model_override=effective_model,
                model_params=model_params, system_prompt=system_prompt,
                file_chunks=ctx["file_chunks"], file_names=ctx["file_names"],
                file_ids=ctx["file_ids"], conv_id=conv.id,
                user_id=current_user.id, db=db,
                image_b64=req.image_b64, image_mime_type=req.image_mime_type,
                graph_context=ctx.get("graph_context", ""),
                graph_facts=ctx.get("graph_facts", ""),
                active_goals=ctx.get("active_goals", ""),
                conflicted_facts=ctx.get("conflicted_facts", frozenset()),
                fact_saliences=ctx.get("fact_saliences", {}),
                last_session=last_session,
                intent=ctx.get("intent", "question"),
            ):
                if event["type"] == "token":
                    accumulated.append(event["content"])
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "preamble_discard":
                    # tokens streamed live were pre-tool preamble — drop them so the
                    # persisted assistant message holds only the real final answer
                    accumulated.clear()
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "status":
                    # behind-the-scenes pipeline step — append to the trace + forward
                    activity.append({k: v for k, v in event.items() if k != "type"})
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] in ("tool_call", "tool_result", "ask_user", "confirm_write_memory"):
                    if event["type"] == "tool_call":
                        tools_in_turn.append(event.get("name", ""))
                    if event["type"] == "ask_user":
                        pending_question = event.get("question", "")
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "done":
                    model_used    = event.get("model", "unknown")
                    cache_hit     = event.get("cache_hit", False)
                    fallback_used = event.get("fallback_used", False)
                    full_response = "".join(accumulated)
                    # S3: compress tool-output regurgitation before persisting
                    persisted_content = compress_tool_dumps(full_response) or pending_question
                    drive_read    = event.get("drive_read", False)
                    drive_file_name = event.get("drive_file_name", "")
 
                    try:
                        pt, ct, tt, cost = _calculate_tokens_and_cost(event, ctx, req, full_response, model_used)
 
                        asst_msg = Message(
                            conversation_id=conv.id, role="assistant",
                            content=persisted_content, model=model_used,
                            prompt_tokens=pt, completion_tokens=ct,
                            total_tokens=tt, cost_usd=cost,
                            activity_trace=activity or None,
                        )
                        db.add(asst_msg)
                        await db.commit()
                        turn_recorded = True
                        record_tokens(model_used, pt, ct, cost)

                        # Drive-read turns: write a REFERENCE, not the body, to avoid
                        # poisoning persistent memory with stale snapshots. The live
                        # tool is the only source of Drive content.
                        if drive_read:
                            _drive_ref = f"User viewed Drive file '{drive_file_name}' — content fetched live, not cached." if drive_file_name else "User viewed a Drive file — content fetched live, not cached."
                            asyncio.create_task(_embed_exchange(asst_msg.id, conv.id, req.message, _drive_ref))
                            from llm.graph_memory import extract_and_store as _graph_extract
                            asyncio.create_task(_graph_extract(current_user.id, req.message, _drive_ref))
                        else:
                            asyncio.create_task(_embed_exchange(asst_msg.id, conv.id, req.message, full_response))
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
                        if not drive_read:
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

                        # Enqueue preference extraction every 50 assistant messages
                        from config import USE_REDIS
                        if USE_REDIS and asst_count > 0 and asst_count % 50 == 0:
                            try:
                                from core.redis_client import get_redis
                                redis = get_redis()
                                lock_key = f"pref_extract:running:{current_user.id}"
                                if not await redis.exists(lock_key):
                                    await redis.set(lock_key, "1", ex=300)
                                    pool = get_arq_pool()
                                    if pool:
                                        await pool.enqueue_job("extract_preferences_job", current_user.id)
                                    else:
                                        from llm.summarizer.preferences import extract_preferences
                                        async def _run_pref_inline(uid: int):
                                            from core.db import AsyncSessionLocal
                                            async with AsyncSessionLocal() as s:
                                                await extract_preferences(uid, s)
                                        asyncio.create_task(_run_pref_inline(current_user.id))
                            except Exception:
                                logger.warning("[preferences] Redis check skipped for user=%s", current_user.id)

                        # Enqueue behavior profile update every reply
                        from core.arq_pool import get_arq_pool
                        bpool = get_arq_pool()
                        if bpool:
                            await bpool.enqueue_job(
                                "update_behavior_profile_job",
                                current_user.id,
                                ctx.get("policy_used", "factual"),
                                req.message,
                                tools_in_turn,
                                model_used,
                            )

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
                    event["provenance"]  = provenance
                    event["query_type"]   = ctx.get("policy_used", "")
                    event["src_count"]    = len(provenance)
                    event["last_session"] = ctx.get("last_session", "")
                    # Reasoning-loop disclosure (Dim 3): grounding confidence +
                    # detected intent + the full pipeline trace, all on one event.
                    event["grounding"] = _compute_grounding(provenance, ctx.get("retrieval_top_k", 5))
                    event["intent"]    = ctx.get("intent", "question")
                    event["activity"]  = activity

                    event["conversation_id"] = conv_id_str
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "error":
                    if accumulated:
                        status = "partial"
                        STREAM_INTERRUPTIONS.inc()
                    else:
                        status = "error"
                    if event.get("message") == "All models failed":
                        ALL_MODELS_FAILED.inc()
                    yield f"data: {_json.dumps(event)}\n\n"
                    await _persist_abort(event.get("message", "tool error"))

        except Exception:
            if accumulated:
                status = "partial"
                STREAM_INTERRUPTIONS.inc()
            else:
                status = "error"
            logger.exception("[chat/stream] failed rid=%s", rid)
            yield f"data: {_json.dumps({'type': 'error', 'message': 'Internal server error'})}\n\n"
            await _persist_abort("internal server error")

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
