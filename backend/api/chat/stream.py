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

from llm.summarizer.history import compress_history
from llm.summarizer.memory import update_memory
from llm.summarizer.project import update_project_summary

from agent.boot import agent_boot, format_boot_log
from agent.scratchpad import update_scratchpad
from agent.node import registry as node_registry, AI_CREATABLE_TYPES

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

_CANVAS_WRITE_TOOLS = frozenset({
    "create_canvas_node", "delete_canvas_node", "update_canvas_node",
    "wire_nodes", "unwire_nodes",
    # this auto-creates + wires a canvas node via _ensure_creation_wiring
    "create_conversation",
})


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

    # Agent boot — health check, scratchpad restore, canvas state
    boot_report = await agent_boot(current_user.id)
    boot_log = format_boot_log(boot_report)
    # type classification owned by agent/node.py (single source of truth)
    _CREATABLE_NODES = [n for n in node_registry if n in AI_CREATABLE_TYPES]
    ni_width = max(len(n) for n in node_registry) + 2
    node_inventory_lines = ["CANVAS LAYOUT:"]
    node_inventory_lines.append("")
    node_inventory_lines.append("PERMANENT nodes (already exist — NEVER call create_canvas_node for these):")
    node_inventory_lines.append("  input    → user's global message input box (sends to this JARVIS conversation)")
    node_inventory_lines.append("  session  → this JARVIS global conversation output — ONE exists, never duplicate it")
    node_inventory_lines.append("  memory   → user memory store")
    node_inventory_lines.append("  config   → model/params settings")
    node_inventory_lines.append("")
    node_inventory_lines.append("CREATABLE nodes (create only when user explicitly asks):")
    for n_name in _CREATABLE_NODES:
        n_def = node_registry[n_name]
        node_inventory_lines.append(f"  {n_name.ljust(ni_width)}→ {n_def.label}")
    node_inventory_lines.append("")

    node_inventory_lines.append("CONFIRMATION PROTOCOL (for creations):")
    node_inventory_lines.append("  If the user's message explicitly mentions creating, starting, or setting")
    node_inventory_lines.append("  up a new session or conversation, respond conversationally:")
    node_inventory_lines.append('    "It seems you want to make a new session. What details should I use?"')
    node_inventory_lines.append("  Wait for the user's reply with name/specs before calling any creation tool.")
    node_inventory_lines.append("")

    node_inventory_lines.append("SESSION CREATION (only after user confirms details):")
    node_inventory_lines.append("  1. call create_conversation(title='<user-given title>') → get conversation_id")
    node_inventory_lines.append("  The session canvas node is created AND wired to the input node automatically.")
    node_inventory_lines.append("  Do NOT call create_canvas_node or wire_nodes for it.")
    node_inventory_lines.append("  These session nodes are SEPARATE threads, not the global JARVIS session.")
    node_inventory_lines.append("")

    node_inventory_lines.append("RULES:")
    node_inventory_lines.append("  - ALWAYS ask for confirmation and specs before creating — never create silently.")
    node_inventory_lines.append("  - create_conversation auto-creates and wires its canvas node — never wire it yourself.")
    node_inventory_lines.append("  - When tools are needed, call them rather than describing actions in text.")
    node_inventory_lines.append("  - Never call create_conversation unless the user explicitly asks to create a session.")
    node_inventory_lines.append("  - Never delete the input node or any node marked [CORE · protected]/[GLOBAL] — they are permanent infrastructure. The session marked [GLOBAL] is the permanent JARVIS session; only [user session] nodes may be deleted. If the user asks to delete 'the session' and only the [GLOBAL] session exists, explain that it is permanent instead of deleting it.")
    node_inventory = "\n".join(node_inventory_lines)

    canvas = boot_report.canvas
    canvas_lines = []
    if canvas.get("nodes"):
        # batch-resolve conversation titles
        import uuid as _uuid_mod
        _conv_ids = []
        for _n in canvas["nodes"]:
            _cfg = _n.get("config", {})
            if _n.get("node_type") == "session" and _cfg.get("conversation_id"):
                _conv_ids.append(_cfg["conversation_id"])
        _conv_titles: dict = {}
        try:
            if _conv_ids:
                _r = await db.execute(
                    select(Conversation.id, Conversation.title)
                    .where(Conversation.id.in_([_uuid_mod.UUID(i) for i in _conv_ids]),
                           Conversation.user_id == current_user.id)
                )
                _conv_titles = {str(r[0]): r[1] for r in _r}
        except Exception:
            pass

        canvas_lines.append("[CANVAS STATE]")
        for n in canvas["nodes"]:
            cfg = n.get("config", {})
            name = cfg.get("name", "")
            if not name and n.get("node_type") == "session":
                name = _conv_titles.get(cfg.get("conversation_id", ""), "")
            name_str = f' "{name}"' if name else ""
            conns = n.get("connections", [])
            conn_str = f" → {len(conns)} connections" if conns else ""
            core_str = " [CORE · protected]" if n.get("protected") else ""
            # H4: make the global session explicit so the model never confuses it
            # with an ordinary user session
            if n.get("node_type") == "session":
                core_str += " [GLOBAL]" if cfg.get("kind") == "global" else " [user session]"
            # full node_id (not truncated) — the model passes these verbatim to delete/update/wire
            canvas_lines.append(f"  {n.get('node_type', '?')}{name_str} ({n.get('node_id', '?')}){core_str}{conn_str}")
    canvas_state = "\n".join(canvas_lines)

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
            last_session=ctx.get("last_session", ""),
            boot_log=boot_log, node_inventory=node_inventory, canvas_state=canvas_state,
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
        last_tool_name: str | None = None

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
                last_session=ctx.get("last_session", ""),
                boot_log=boot_log, node_inventory=node_inventory, canvas_state=canvas_state,
            ):
                if event["type"] == "token":
                    accumulated.append(event["content"])
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] == "preamble_discard":
                    # tokens streamed live were pre-tool preamble — drop them so the
                    # persisted assistant message holds only the real final answer
                    accumulated.clear()
                    yield f"data: {_json.dumps(event)}\n\n"

                elif event["type"] in ("tool_call", "tool_result", "ask_user", "confirm_write_memory"):
                    if event["type"] == "tool_call":
                        tools_in_turn.append(event.get("name", ""))
                        last_tool_name = event.get("name", "")
                    if event["type"] == "ask_user":
                        pending_question = event.get("question", "")
                    yield f"data: {_json.dumps(event)}\n\n"
                    if event["type"] == "tool_result" and last_tool_name in _CANVAS_WRITE_TOOLS:
                        yield f"data: {_json.dumps({'type': 'canvas_update'})}\n\n"

                elif event["type"] == "done":
                    model_used    = event.get("model", "unknown")
                    cache_hit     = event.get("cache_hit", False)
                    fallback_used = event.get("fallback_used", False)
                    full_response = "".join(accumulated)

                    try:
                        pt, ct, tt, cost = _calculate_tokens_and_cost(event, ctx, req, full_response, model_used)

                        asst_msg = Message(
                            conversation_id=conv.id, role="assistant",
                            content=full_response or pending_question, model=model_used,
                            prompt_tokens=pt, completion_tokens=ct,
                            total_tokens=tt, cost_usd=cost,
                        )
                        db.add(asst_msg)
                        await db.commit()
                        record_tokens(model_used, pt, ct, cost)
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

                        # Save agent scratchpad (append-only merge)
                        from datetime import datetime, timezone
                        try:
                            await update_scratchpad(current_user.id, {
                                "last_message": req.message[:200],
                                "summary": req.message[:120],
                                "last_action": "chat_response",
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            })
                        except Exception:
                            logger.warning("[scratchpad] update failed rid=%s", rid)

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

        except Exception:
            if accumulated:
                status = "partial"
                STREAM_INTERRUPTIONS.inc()
            else:
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
