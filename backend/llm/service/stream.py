import asyncio
import base64
import json
import logging
import time
import uuid

from sqlalchemy import select

import config
from config import MODEL_VISION, USE_REDIS, WEB_SEARCH_ENABLED, IMAGE_OCR_ENABLED
from cache import get_cached_response, set_cached_response
from observability import metrics, observability, events
from llm.router import route, get_context_limit
from llm.nim import call, call_stream
from llm.tools import execute_tool, ASK_USER_PREFIX, CONFIRM_WRITE_PREFIX, CONFIRM_CALENDAR_PREFIX, TOOL_REGISTRY, ToolContext, get_tool, select_tool_schemas

from models import ExternalSource
from .context import build_context_messages, apply_context_budget, _needs_memory_tool

MAX_TOOL_ITERATIONS = 60
# Runaway-loop guard: abort when the SAME tool is called with the SAME args
# too many times. Keyed on (name, args) signature, so legit bulk work flows
# freely while a true loop (identical repeated call) still trips. Distinct-arg
# volume is bounded by MAX_TOOL_ITERATIONS.
_MAX_IDENTICAL_CALLS = 3
# Per-tool overrides (e.g. listing tools → 1) come from Tool.max_identical_calls.

logger = logging.getLogger("service")
# Phase 0 instrumentation: one JSON line per turn carrying every connector-intent score and
# the flip/no-flip decision, so traffic can be replayed into eval sets (none_intent /
# weak_real / tie) without re-running the model. Distinct logger name → greppable / routable
# (`grep '"evt": "latch_score"'`) without drowning in the service log.
latch_logger = logging.getLogger("connector_intent.scores")


async def _resolve_connector_latches(actives: dict, latched: dict, conv_id, query_emb,
                                     embed_status: str = "ok", *, message: str = "",
                                     turn: int | None = None) -> dict:
    """Resolve all connector session intent latches for this turn (Q3 Task B + generalization).

    Single-winner: already-latched connectors stay latched (sticky; TTL refreshed). Among
    ACTIVE, not-yet-latched connectors, score query_emb vs each centroid and latch ONLY the
    top scorer if it clears BOTH its per-connector threshold AND the global floor
    (`FLOOR_THRESHOLD=0.65`; `{connector}_latched:{conv_id}`, ex=3600,
    latch-then-serve same turn). Single-winner stops one connector's request from latching
    the others (the connectors share a "check my X" structure → high cross-talk), so a
    cross-talk/task-imperative false latch hits one connector, not all. The floor prevents
    latching on a weak winner that only "won" because every score was low.

    USE_REDIS off → same-turn score only (no cross-turn stickiness); never falls back to
    capability-only (that reinstates the over-fire bug). query_emb None → all scores 0.0.

    Phase 0: ALL three connectors are scored every turn (not just the active+unlatched flip
    candidates) so the structured log captures cross-talk — the flip itself still considers
    only the active, not-yet-latched subset, so behavior is unchanged. Returns the updated
    latched dict.
    """
    from llm.tools.connector_intent import intent_score, INTENT_THRESHOLDS, FLOOR_THRESHOLD, INTENT_PHRASES
    out = dict(latched)

    # Sticky: refresh TTL on connectors already latched this session.
    if conv_id and USE_REDIS:
        for c, on in latched.items():
            if actives.get(c) and on:
                try:
                    from core.redis_client import get_redis
                    await get_redis().expire(f"{c}_latched:{conv_id}", 3600)
                except Exception:
                    pass

    # Score ALL connectors (cross-talk observability); the flip considers only the active,
    # not-yet-latched subset. Cheap: reuses query_emb + pre-warmed centroids.
    all_scores = {c: await intent_score(c, query_emb) for c in INTENT_PHRASES}
    candidates = {c: all_scores[c] for c in actives if actives.get(c) and not latched.get(c)}

    winner = None
    decision = "none"
    why = "no_active_unlatched_candidate"
    if candidates:
        winner = max(candidates, key=candidates.get)
        s = all_scores[winner]
        if s >= INTENT_THRESHOLDS[winner] and s >= FLOOR_THRESHOLD:
            out[winner] = True
            decision = f"latched_{winner}"
            why = f"{s:.3f} >= max(thr {INTENT_THRESHOLDS[winner]:.2f}, floor {FLOOR_THRESHOLD:.2f})"
            if conv_id and USE_REDIS:
                try:
                    from core.redis_client import get_redis
                    await get_redis().set(f"{winner}_latched:{conv_id}", "1", ex=3600)
                except Exception:
                    pass
        elif s < FLOOR_THRESHOLD:
            why = f"winner {winner} {s:.3f} < floor {FLOOR_THRESHOLD:.2f}"
        else:
            why = f"winner {winner} {s:.3f} < per-connector thr {INTENT_THRESHOLDS[winner]:.2f}"

    # Structured per-turn score log (Phase 0; one JSON line per turn for eval-set building).
    try:
        ranked = sorted(all_scores.items(), key=lambda kv: kv[1], reverse=True)
        argmax_c, argmax_s = ranked[0]
        runner_c, runner_s = ranked[1] if len(ranked) > 1 else (None, 0.0)
        reason = {"ok": "ok", "failed": "embed_fail", "skipped": "rag_skip"}.get(embed_status, embed_status)
        latch_logger.info(json.dumps({
            "evt": "latch_score",
            "conv_id": str(conv_id) if conv_id else None,
            "turn": turn,
            "query_emb_present": bool(query_emb),
            "reason": reason,
            "scores": {c: round(s, 4) for c, s in all_scores.items()},
            "prior_latch_state": {c: bool(latched.get(c)) for c in INTENT_PHRASES},
            "active": {c: bool(actives.get(c)) for c in INTENT_PHRASES},
            "argmax": argmax_c, "argmax_score": round(argmax_s, 4),
            "runner_up": runner_c, "runner_up_score": round(runner_s, 4),
            "margin": round(argmax_s - runner_s, 4),
            "decision": decision,
            "why": why,
            "msg": (message or "")[:120],
        }, ensure_ascii=False))
    except Exception:
        logger.warning("[latch] score-log failed", exc_info=True)

    return out


async def generate_response(message: str, request_id: str) -> dict:
    total_start = time.monotonic()

    try:
        await observability.publish_request_event(
            events.request_event(request_id=request_id)
        )
    except Exception:
        pass

    cached = await get_cached_response(message)  # non-streaming: no history context
    if cached:
        return {
            "response":      cached["response"],
            "model":         cached.get("model", "cache"),
            "cache_hit":     True,
            "fallback_used": False,
            "latency_ms":    0,
        }

    model, _ = await route(message, request_id)
    fallback_chain = [model] + [config.MODELS[k] for k in config.FALLBACK_ORDER if config.MODELS[k] != model]

    for idx, current_model in enumerate(fallback_chain):
        fallback_used = idx > 0
        result  = await call(current_model, [{"role": "user", "content": message}], request_id)
        content = result.get("content")

        if not isinstance(content, str) or not content.strip():
            logger.warning("[service] empty_content model=%s error=%s", current_model, result.get("error"))
            continue

        payload = {
            "response":      content.strip(),
            "model":         current_model,
            "cache_hit":     False,
            "fallback_used": fallback_used,
            "latency_ms":    result.get("latency_ms", 0),
            "usage":         result.get("usage"),
        }

        try:
            await set_cached_response(message, payload)
            metrics.record_cache_write()
        except Exception as e:
            logger.warning("[cache] write_failed err=%s", e)

        if fallback_used:
            metrics.record_fallback()

        return payload

    return {
        "response":      "All models failed. Please try again later.",
        "model":         "none",
        "cache_hit":     False,
        "fallback_used": True,
        "latency_ms":    (time.monotonic() - total_start) * 1000,
    }


async def generate_stream(
    message:          str,
    history:          list[dict],
    memory_sheet:     str,
    project_summary:  str,
    history_summary:  str,
    retrieved_chunks: list[str],
    request_id:       str,
    model_override:   str | None        = None,
    model_params:     dict | None       = None,
    system_prompt:    str | None        = None,
    file_chunks:      list[str]         = (),
    file_names:       list[str]         = (),
    file_ids:         list              = (),
    conv_id:          uuid.UUID | None  = None,
    user_id:          int | None        = None,
    db                                  = None,
    image_b64:        str | None        = None,
    image_mime_type:  str | None        = None,
    graph_context:    str               = "",
    graph_facts:      str               = "",
    active_goals:     str               = "",
    recent_insights:  list[str]         = (),
    conflicted_facts: frozenset         = frozenset(),
    fact_saliences:   dict | None       = None,
    last_session:     str               = "",
    intent:           str               = "question",
    query_emb:        list | None       = None,
    embed_status:     str               = "ok",
):
    # Cache excludes file/image/custom-params requests; history + model included in key
    use_cache = not file_chunks and not image_b64 and not model_params
    history_tail  = "\n".join(m["content"] for m in (history or [])[-4:])
    cache_model   = model_override or ""
    cache_sysprompt = system_prompt or ""

    if use_cache:
        cached = await get_cached_response(
            message,
            model=cache_model,
            history_tail=history_tail,
            system_prompt=cache_sysprompt,
        )
        if cached:
            yield {"type": "status", "stage": "cache", "detail": "Cache hit — returning stored answer", "level": "info"}
            yield {"type": "token", "content": cached["response"]}
            yield {"type": "done",  "model": cached.get("model", "cache"), "cache_hit": True, "fallback_used": False, "web_searched": False, "url_fetched": False}
            return

    # Model selection priority: image → explicit override → file tools → memory write → router
    if image_b64 and not IMAGE_OCR_ENABLED:
        fallback_chain = [MODEL_VISION]
        route_reason = "vision"
    elif model_override:
        fallback_chain = [model_override] + [config.MODELS[k] for k in config.FALLBACK_ORDER if config.MODELS[k] != model_override]
        route_reason = "override"
    elif file_ids:
        # Always use reasoning model when files attached — 8B cannot reliably use tool results
        fallback_chain = [config.MODELS["reasoning"]]
        route_reason = "files"
    elif _needs_memory_tool(message):
        fallback_chain = [config.MODELS["reasoning"]] + [config.MODELS[k] for k in config.FALLBACK_ORDER if config.MODELS[k] != config.MODELS["reasoning"]]
        route_reason = "memory"
    elif intent == "task":
        # Task intent → tool-eager. Prefer the reasoning model (8B emits tool
        # calls as plain text); keep the rest of the chain as fallback.
        fallback_chain = [config.MODELS["reasoning"]] + [config.MODELS[k] for k in config.FALLBACK_ORDER if config.MODELS[k] != config.MODELS["reasoning"]]
        route_reason = "task-intent"
    else:
        model, _ = await route(message, request_id)
        fallback_chain = [model] + [config.MODELS[k] for k in config.FALLBACK_ORDER if config.MODELS[k] != model]
        route_reason = "router"

    yield {"type": "status", "stage": "route", "detail": f"Routing → {fallback_chain[0]} ({route_reason})", "level": "info"}

    # Resolve async connector flags ONCE here so each tool's should_inject() stays a
    # pure, synchronous predicate. Then offer whichever registered tools opt in.
    _is_reasoning = fallback_chain[0] == config.MODELS["reasoning"]
    _drive_active = False
    _drive_cache_active = False
    _drive_latched = False
    _calendar_active = False
    _calendar_latched = False
    _gmail_active = False
    _gmail_latched = False
    if db is not None:
        async def _connector_active(connector_type: str) -> bool:
            return bool(await db.scalar(
                select(ExternalSource.id).where(
                    ExternalSource.user_id == user_id,
                    ExternalSource.connector_type == connector_type,
                    ExternalSource.status == "active",
                )
            ))
        _drive_active = await _connector_active("google_drive")
        _calendar_active = await _connector_active("google_calendar")
        _gmail_active = await _connector_active("gmail")
        if conv_id and USE_REDIS:
            try:
                from core.redis_client import get_redis
                _redis = get_redis()
                if _drive_active:
                    _drive_cache_active = bool(await _redis.exists(f"drive_listing:{conv_id}"))
                    _drive_latched = bool(await _redis.exists(f"drive_latched:{conv_id}"))
                if _calendar_active:
                    _calendar_latched = bool(await _redis.exists(f"calendar_latched:{conv_id}"))
                if _gmail_active:
                    _gmail_latched = bool(await _redis.exists(f"gmail_latched:{conv_id}"))
            except Exception:
                pass

    # Per-connector intent latch (Q3 Task B + calendar/gmail generalization). Withhold
    # each connector's schemas until genuine intent for THAT connector appears, then latch
    # it in for the session. Single-winner across connectors (one request can't latch the
    # others — they share a "check my X" structure → high cross-talk). Runs BEFORE the
    # injected_tools assembly below so the schema serves THIS turn (latch-then-serve) — the
    # first real connector request isn't a dead turn. Reuses query_emb; no new embed call.
    # The cosine signal is a learned embedding match, not a keyword rule. One flip per
    # connector per session → one prefix-cache miss, then the schema block is byte-stable.
    _latched = await _resolve_connector_latches(
        {"drive": _drive_active, "calendar": _calendar_active, "gmail": _gmail_active},
        {"drive": _drive_latched, "calendar": _calendar_latched, "gmail": _gmail_latched},
        conv_id, query_emb, embed_status,
        message=message, turn=len(history or []),
    )
    _drive_latched, _calendar_latched, _gmail_latched = (
        _latched["drive"], _latched["calendar"], _latched["gmail"])

    _tool_ctx = ToolContext(
        message=message,
        history=history or [],
        db=db,
        user_id=user_id,
        conv_id=conv_id,
        file_ids=tuple(file_ids or ()),
        is_reasoning=_is_reasoning,
        web_search_enabled=WEB_SEARCH_ENABLED,
        use_redis=USE_REDIS,
        drive_active=_drive_active,
        drive_cache_active=_drive_cache_active,
        drive_latched=_drive_latched,
        calendar_active=_calendar_active,
        calendar_latched=_calendar_latched,
        gmail_active=_gmail_active,
        gmail_latched=_gmail_latched,
    )
    # Capability-available tools, name-sorted for a byte-stable prompt prefix
    # (so the KV prefix cache makes repeat cost near-zero). The prefilter switch
    # decides the final subset; today it is passthrough. Reconcile injected_tools
    # to the survivors so behavioral_rules stay consistent if the prefilter later
    # drops a tool.
    injected_tools = sorted(
        (t for t in TOOL_REGISTRY.values() if t.should_inject(_tool_ctx)),
        key=lambda t: t.name,
    )
    schemas = select_tool_schemas(message, [t.schema for t in injected_tools])
    _kept = {s["function"]["name"] for s in schemas}
    injected_tools = [t for t in injected_tools if t.name in _kept]
    tools = schemas or None

    # Closing turn (pure thanks/goodbye/ack, classified upstream): keep it a plain
    # chat turn. No tools and no connector clarify nudge → llama stays in the chain
    # (see the llama-drop guard below) so a goodbye gets a one-line ack from the
    # cheap keyword-routed model instead of the tool-eager reasoning model.
    _closing = intent == "closing"
    if _closing:
        injected_tools = []
        tools = None

    # Tool-required turns (file ops) must not degrade to 8B — it emits tool
    # calls as plain text instead of using the tool-calling API. Drop llama from the
    # fallback chain when tools are active, but never leave the chain empty.
    if tools and config.MODELS["llama"] in fallback_chain:
        _tool_capable = [m for m in fallback_chain if m != config.MODELS["llama"]]
        if _tool_capable:
            fallback_chain = _tool_capable

    if image_b64 and image_mime_type:
        if IMAGE_OCR_ENABLED:
            import io
            from services.processor import extract_image_from_bytes
            img_bytes = base64.b64decode(image_b64)
            ocr_text = await asyncio.to_thread(extract_image_from_bytes, img_bytes)
            if ocr_text.strip():
                user_msg = {"role": "user", "content": f"{message}\n\n[Image content detected via OCR:]\n{ocr_text[:5000]}"}
                yield {"type": "status", "stage": "ocr", "detail": f"OCR extracted {len(ocr_text)} chars from pasted image", "level": "info"}
            else:
                user_msg = {"role": "user", "content": f"{message}\n\n[No text detected in the pasted image.]"}
                yield {"type": "status", "stage": "ocr", "detail": "No text found in pasted image", "level": "info"}
        else:
            user_content = [
                {"type": "text", "text": message},
                {"type": "image_url", "image_url": {"url": f"data:{image_mime_type};base64,{image_b64}"}},
            ]
            user_msg = {"role": "user", "content": user_content}
    else:
        user_msg = {"role": "user", "content": message}

    # Strip aborted-turn markers from history — they confuse the model into
    # re-calling the same tool trying to "fix" the previous failure.
    _clean_history = []
    for msg in (history or []):
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), str) and msg["content"].startswith("⚠️ Turn aborted"):
            _clean_history.append({"role": "assistant", "content": "I encountered an error on that request. Please try again."})
        else:
            _clean_history.append(msg)

    base_messages = build_context_messages(
        memory_sheet, project_summary, retrieved_chunks, history_summary,
        _clean_history, system_prompt, file_chunks, file_names, file_ids,
        graph_context=graph_context,
        graph_facts=graph_facts, active_goals=active_goals,
        recent_insights=recent_insights,
        conflicted_facts=conflicted_facts, last_session=last_session,
        intent=intent,
    ) + [user_msg]

    # Inject active tools' behavioral rules once (de-duped), as a single block at
    # base_messages[1] in deterministic (name-sorted) order — keeps the prompt
    # prefix byte-stable for the KV cache. injected_tools is already name-sorted.
    _seen_rules: set[str] = set()
    _rules_block: list[dict] = []
    for t in injected_tools:
        if t.behavioral_rules and t.behavioral_rules not in _seen_rules:
            _seen_rules.add(t.behavioral_rules)
            _rules_block.append({"role": "system", "content": t.behavioral_rules})

    # Clarify fallback (fork-B). For connectors that are ACTIVE but NOT latched this turn (the
    # under-fire case), the schemas + their behavioral_rules are withheld — so without this the
    # model doesn't even know the connector exists and can't ask "which X?". Inject a lightweight,
    # latch-INDEPENDENT nudge (no schemas → schemas stay withheld, KV prefix stays byte-stable) so
    # an ambiguous terse request ("get that document") gets a clarifying question instead of a dead
    # end. The latch is precision-biased (under-fires genuine terse requests on purpose); this is
    # what recovers them. Deterministic connector order.
    _CLARIFY_SVC = {"drive": "Google Drive (files/documents)",
                    "calendar": "Google Calendar (schedule/events)",
                    "gmail": "Gmail (email/inbox)"}
    _unlatched = [c for c, on, lat in (
        ("drive", _drive_active, _drive_latched),
        ("calendar", _calendar_active, _calendar_latched),
        ("gmail", _gmail_active, _gmail_latched),
    ) if on and not lat]
    if _unlatched and not _closing:
        _svc = "; ".join(_CLARIFY_SVC[c] for c in _unlatched)
        _rules_block.append({"role": "system", "content": (
            "## Connected services (tools not loaded this turn)\n\n"
            f"The user has connected: {_svc}. Those tools are NOT available on THIS turn (the current "
            "message wasn't a clear request for them). Do NOT claim you lack access to them.\n\n"
            "When the message is a vague fetch/lookup — a verb like get / find / open / pull up / grab "
            "/ check / show me / look up with NO clear object AND no obvious referent already in this "
            "conversation (e.g. \"get that document\", \"pull that up for me\", \"find it\", \"any new "
            "mail\", \"what's next\") — it most likely wants one of the connected services but is too "
            "vague to act on. In that case ask ONE short clarifying question that NAMES the service — "
            "e.g. \"Do you mean a file in your Google Drive? Which one?\". A clearer follow-up loads the "
            "tools next turn.\n\n"
            "Escape hatch: if the message clearly refers to something already in THIS conversation, or "
            "is a normal question/task unrelated to files/schedule/email, just answer normally — do NOT "
            "ask about the connected services."
        )})
    if _rules_block:
        base_messages[1:1] = _rules_block

    for idx, current_model in enumerate(fallback_chain):
        fallback_used  = idx > 0
        if fallback_used:
            yield {"type": "status", "stage": "fallback", "detail": f"Falling back → {current_model}", "level": "error"}
        tool_messages  = list(base_messages)
        ctx_window = get_context_limit(current_model)
        max_out = (model_params or {}).get("max_tokens", 4096)
        if not isinstance(max_out, int):
            try:
                max_out = int(max_out)
            except (TypeError, ValueError):
                max_out = 4096
        tool_messages = apply_context_budget(tool_messages, ctx_window, max_out, fact_saliences=fact_saliences)
        if idx == 0:
            yield {"type": "status", "stage": "budget", "detail": f"Context fitted to {ctx_window:,}-tok window (≤{max_out:,} out)", "level": "info"}
        model_done     = False
        tool_call_counts: dict[tuple[str, str], int] = {}
        _force_no_tools = False  # set after a loop-guard trip → final turn answers in text
        _web_searched = False
        _url_fetched  = False
        _drive_read = False
        _drive_file_name = ""

        for _tool_iter in range(MAX_TOOL_ITERATIONS):
            accumulated      = []
            started          = False
            tool_calls_done  = None
            stream_broke     = False
            nim_usage        = None

            _t_call = time.monotonic()
            try:
                async for chunk in call_stream(current_model, tool_messages, request_id, model_params, None if _force_no_tools else tools):
                    if isinstance(chunk, dict) and "__tool_calls__" in chunk:
                        tool_calls_done = chunk["__tool_calls__"]
                    elif isinstance(chunk, dict) and "__usage__" in chunk:
                        nim_usage = chunk["__usage__"]
                    elif isinstance(chunk, str):
                        started = True
                        accumulated.append(chunk)
                        yield {"type": "token", "content": chunk}

                _call_ms = int((time.monotonic() - _t_call) * 1000)
                _short = current_model.split("/")[-1]
                if tool_calls_done:
                    _names = ", ".join(tc["function"]["name"] for tc in tool_calls_done)
                    yield {"type": "status", "stage": "model_call", "detail": f"{_short} → requested tool(s): {_names}", "level": "info", "ms": _call_ms}
                else:
                    yield {"type": "status", "stage": "model_call", "detail": f"{_short} → response", "level": "info", "ms": _call_ms}

                # Model streamed preamble text and THEN requested a tool call.
                # Tokens already went out live; tell the client to drop that
                # preamble — the real answer arrives after the tool result on a
                # later iteration. Avoids the preamble being duplicated/persisted.
                if tool_calls_done and accumulated:
                    yield {"type": "preamble_discard"}
                    accumulated.clear()
            except Exception as e:
                logger.warning("[service] stream_failed model=%s started=%s err=%s", current_model, started, e)
                if started:
                    yield {"type": "error", "message": "Stream interrupted"}
                    return
                stream_broke = True
                break

            if stream_broke:
                break

            if tool_calls_done:
                ask_user_triggered = False
                for tc in tool_calls_done:
                    fn_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}

                    # Signature = name + canonical args. Identical repeats are a
                    # loop (same delete/create/query over and over); distinct
                    # args (bulk delete of different node_ids) are legit work.
                    # Strip None values so {"query": null} and {} hash identically.
                    _norm = {k: v for k, v in args.items() if v is not None}
                    sig = (fn_name, json.dumps(_norm, sort_keys=True, default=str))
                    tool_call_counts[sig] = tool_call_counts.get(sig, 0) + 1
                    _tool_def = get_tool(fn_name)
                    _call_limit = _tool_def.max_identical_calls if (_tool_def and _tool_def.max_identical_calls is not None) else _MAX_IDENTICAL_CALLS
                    if tool_call_counts[sig] > _call_limit:
                        logger.warning("[service] tool_loop_guard: %s called %d times with identical args, forcing text answer", fn_name, tool_call_counts[sig])
                        yield {"type": "status", "stage": "tool", "detail": f"Stopping repeated {fn_name} calls — answering with available info", "level": "error"}
                        # Don't abort to an empty reply. Force one final tool-free turn so the
                        # model responds in text, relaying any tool error already in context
                        # (e.g. a 403 "reconnect the integration" message) to the user.
                        tool_messages.append({"role": "system", "content": (
                            f"You have called {fn_name} repeatedly with identical arguments and it is "
                            f"not returning new information. Stop calling tools now and reply to the user "
                            f"directly, using what you already have — including relaying verbatim any error "
                            f"or instruction the tool returned (such as reconnecting an integration)."
                        )})
                        _force_no_tools = True
                        break

                    yield {"type": "tool_call", "name": fn_name, "args": args}
                    args_summary = json.dumps(args, sort_keys=True)[:80]
                    yield {"type": "status", "stage": "tool", "detail": f"Called: {fn_name}({args_summary})", "level": "info"}
                    _t_tool = time.monotonic()
                    result = await execute_tool(fn_name, args, db, user_id, conv_id)
                    _tool_ms = int((time.monotonic() - _t_tool) * 1000)
                    result_snippet = str(result)[:100]
                    yield {"type": "status", "stage": "tool_result", "detail": f"{fn_name}: {result_snippet}", "level": "info", "ms": _tool_ms}

                    if result.startswith(ASK_USER_PREFIX):
                        question = result[len(ASK_USER_PREFIX):]
                        yield {"type": "ask_user", "question": question}
                        done_ev = {"type": "done", "model": current_model, "cache_hit": False, "fallback_used": fallback_used, "web_searched": _web_searched, "url_fetched": _url_fetched, "drive_read": _drive_read, "drive_file_name": _drive_file_name}
                        if nim_usage:
                            done_ev["usage"] = nim_usage
                        yield done_ev
                        ask_user_triggered = True
                        break

                    if result.startswith(CONFIRM_WRITE_PREFIX):
                        fact = result[len(CONFIRM_WRITE_PREFIX):]
                        yield {"type": "confirm_write_memory", "fact": fact}
                        done_ev = {"type": "done", "model": current_model, "cache_hit": False, "fallback_used": fallback_used, "web_searched": _web_searched, "url_fetched": _url_fetched, "drive_read": _drive_read, "drive_file_name": _drive_file_name}
                        if nim_usage:
                            done_ev["usage"] = nim_usage
                        yield done_ev
                        ask_user_triggered = True
                        break

                    if result.startswith(CONFIRM_CALENDAR_PREFIX):
                        payload = json.loads(result[len(CONFIRM_CALENDAR_PREFIX):])
                        yield {"type": "confirm_calendar_write", **payload}
                        done_ev = {"type": "done", "model": current_model, "cache_hit": False, "fallback_used": fallback_used, "web_searched": _web_searched, "url_fetched": _url_fetched, "drive_read": _drive_read, "drive_file_name": _drive_file_name}
                        if nim_usage:
                            done_ev["usage"] = nim_usage
                        yield done_ev
                        ask_user_triggered = True
                        break

                    if fn_name == "web_search":
                        _web_searched = True
                    if fn_name == "fetch_url":
                        _url_fetched = True
                    if fn_name == "drive_read_file":
                        _drive_read = True
                        if result.startswith("--- ") and " ---" in result:
                            _drive_file_name = result[4:result.index(" ---")]

                    yield {"type": "tool_result", "name": fn_name, "content": result[:500]}
                    tool_messages.append({"role": "assistant", "tool_calls": [tc]})
                    tool_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result[:12000]})

                    # After a listing tool returns, force the model to respond in text
                    # (declared per-tool via post_call_system_msg) — without this the 70B
                    # re-calls the listing tool instead of presenting.
                    if _tool_def and _tool_def.post_call_system_msg:
                        tool_messages.append({"role": "system", "content": _tool_def.post_call_system_msg})

                if ask_user_triggered:
                    return

                tool_messages = apply_context_budget(tool_messages, ctx_window, max_out, fact_saliences=fact_saliences)
                continue

            if not accumulated:
                logger.warning("[service] empty_stream model=%s", current_model)
                break

            full_response = "".join(accumulated)
            payload = {
                "response":      full_response,
                "model":         current_model,
                "cache_hit":     False,
                "fallback_used": fallback_used,
            }
            if use_cache:
                try:
                    await set_cached_response(
                        message, payload,
                        # key must mirror the read side (model_override or ""), not the
                        # routed model — otherwise auto-routed requests can never hit
                        model=cache_model,
                        history_tail=history_tail,
                        system_prompt=cache_sysprompt,
                    )
                    metrics.record_cache_write()
                except Exception as e:
                    logger.warning("[cache] write_failed err=%s", e)
            if fallback_used:
                metrics.record_fallback()

            done_ev = {"type": "done", "model": current_model, "cache_hit": False, "fallback_used": fallback_used, "web_searched": _web_searched, "url_fetched": _url_fetched, "drive_read": _drive_read, "drive_file_name": _drive_file_name}
            if nim_usage:
                done_ev["usage"] = nim_usage
            yield done_ev
            model_done = True
            break

        else:
            yield {"type": "error", "message": "Tool loop limit reached"}
            return

        if model_done:
            return

    yield {"type": "error", "message": "All models failed"}
