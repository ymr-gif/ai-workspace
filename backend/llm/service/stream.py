import json
import logging
import time
import uuid

from sqlalchemy import select

from config import FALLBACK_ORDER, MODEL_VISION, MODELS, USE_REDIS, WEB_SEARCH_ENABLED
from cache import get_cached_response, set_cached_response
from observability import metrics, observability, events
from llm.router import route, get_context_limit
from llm.nim import call, call_stream
from llm.tools import execute_tool, ASK_USER_PREFIX, CONFIRM_WRITE_PREFIX, TOOL_REGISTRY, ToolContext, get_tool

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
    fallback_chain = [model] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != model]

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
    if image_b64:
        fallback_chain = [MODEL_VISION]
        route_reason = "vision"
    elif model_override:
        fallback_chain = [model_override] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != model_override]
        route_reason = "override"
    elif file_ids:
        # Always use reasoning model when files attached — 8B cannot reliably use tool results
        fallback_chain = [MODELS["reasoning"]]
        route_reason = "files"
    elif _needs_memory_tool(message):
        fallback_chain = [MODELS["reasoning"]] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != MODELS["reasoning"]]
        route_reason = "memory"
    elif intent == "task":
        # Task intent → tool-eager. Prefer the reasoning model (8B emits tool
        # calls as plain text); keep the rest of the chain as fallback.
        fallback_chain = [MODELS["reasoning"]] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != MODELS["reasoning"]]
        route_reason = "task-intent"
    else:
        model, _ = await route(message, request_id)
        fallback_chain = [model] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != model]
        route_reason = "router"

    yield {"type": "status", "stage": "route", "detail": f"Routing → {fallback_chain[0]} ({route_reason})", "level": "info"}

    # Resolve async Drive flags ONCE here so each tool's should_inject() stays a
    # pure, synchronous predicate. Then offer whichever registered tools opt in.
    _is_reasoning = fallback_chain[0] == MODELS["reasoning"]
    _drive_active = False
    _drive_cache_active = False
    if db is not None:
        _drive_active = bool(await db.scalar(
            select(ExternalSource.id).where(
                ExternalSource.user_id == user_id,
                ExternalSource.connector_type == "google_drive",
                ExternalSource.status == "active",
            )
        ))
        if _drive_active and conv_id and USE_REDIS:
            try:
                from core.redis_client import get_redis
                _drive_cache_active = bool(await get_redis().exists(f"drive_listing:{conv_id}"))
            except Exception:
                pass

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
    )
    injected_tools = [t for t in TOOL_REGISTRY.values() if t.should_inject(_tool_ctx)]
    tools = [t.schema for t in injected_tools] or None

    # Tool-required turns (file ops) must not degrade to 8B — it emits tool
    # calls as plain text instead of using the tool-calling API. Drop llama from the
    # fallback chain when tools are active, but never leave the chain empty.
    if tools and MODELS["llama"] in fallback_chain:
        _tool_capable = [m for m in fallback_chain if m != MODELS["llama"]]
        if _tool_capable:
            fallback_chain = _tool_capable

    if image_b64 and image_mime_type:
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
    ) + [user_msg]

    # Inject each active tool's behavioral rules once (de-duped) at base_messages[1].
    _seen_rules: set[str] = set()
    for t in injected_tools:
        if t.behavioral_rules and t.behavioral_rules not in _seen_rules:
            _seen_rules.add(t.behavioral_rules)
            base_messages.insert(1, {"role": "system", "content": t.behavioral_rules})

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
                async for chunk in call_stream(current_model, tool_messages, request_id, model_params, tools):
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
                        logger.warning("[service] tool_loop_guard: %s called %d times with identical args, aborting", fn_name, tool_call_counts[sig])
                        yield {"type": "error", "message": f"Tool loop detected: {fn_name} called repeatedly with the same arguments"}
                        return

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
                        model=current_model,
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
