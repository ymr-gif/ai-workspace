import json
import logging
import time
import uuid

from config import FALLBACK_ORDER, MODEL_VISION, MODELS
from cache import get_cached_response, set_cached_response
from observability import metrics, observability, events
from llm.router import route, get_context_limit
from llm.nim import call, call_stream
from llm.tools import TOOL_SCHEMAS, FILE_TOOL_SCHEMAS, CANVAS_TOOL_SCHEMAS, WRITE_MEMORY_SCHEMA, execute_tool, ASK_USER_PREFIX, CONFIRM_WRITE_PREFIX

from .context import build_context_messages, _needs_file_tools, _needs_memory_tool, apply_context_budget

MAX_TOOL_ITERATIONS = 20
_READONLY_CANVAS_TOOLS = frozenset({"get_canvas_graph", "query_canvas"})

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
    conflicted_facts: frozenset         = frozenset(),
    fact_saliences:   dict | None       = None,
    last_session:     str               = "",
    boot_log:         str               = "",
    node_inventory:   str               = "",
    canvas_state:     str               = "",
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
            yield {"type": "token", "content": cached["response"]}
            yield {"type": "done",  "model": cached.get("model", "cache"), "cache_hit": True, "fallback_used": False}
            return

    # Model selection priority: image → explicit override → file tools → memory write → router
    if image_b64:
        fallback_chain = [MODEL_VISION]
    elif model_override:
        fallback_chain = [model_override] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != model_override]
    elif file_ids:
        # Always use reasoning model when files attached — 8B cannot reliably use tool results
        fallback_chain = [MODELS["reasoning"]]
    elif _needs_memory_tool(message):
        fallback_chain = [MODELS["reasoning"]] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != MODELS["reasoning"]]
    else:
        model, _ = await route(message, request_id)
        fallback_chain = [model] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != model]

    file_tools   = FILE_TOOL_SCHEMAS   if (file_ids and db is not None) else []
    canvas_tools = CANVAS_TOOL_SCHEMAS if (db is not None and node_inventory) else []

    # write_memory: reasoning model only + user must explicitly request save (prevents 70B saving on its own initiative)
    _is_reasoning = fallback_chain[0] == MODELS["reasoning"]
    mem_tools = [WRITE_MEMORY_SCHEMA] if (db is not None and _is_reasoning and _needs_memory_tool(message)) else []
    # deduplicate by tool name (file_tools already contains canvas tools when both active)
    _seen, tools_list = set(), []
    for t in (file_tools + canvas_tools + mem_tools):
        n = t["function"]["name"]
        if n not in _seen:
            _seen.add(n)
            tools_list.append(t)
    tools = tools_list or None

    # Tool-required turns (canvas/file ops) must not degrade to 8B — it emits tool
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

    base_messages = build_context_messages(
        memory_sheet, project_summary, retrieved_chunks, history_summary,
        history, system_prompt, file_chunks, file_names, file_ids,
        graph_context=graph_context,
        graph_facts=graph_facts, active_goals=active_goals,
        conflicted_facts=conflicted_facts, last_session=last_session,
        boot_log=boot_log, node_inventory=node_inventory, canvas_state=canvas_state,
    ) + [user_msg]

    for idx, current_model in enumerate(fallback_chain):
        fallback_used  = idx > 0
        tool_messages  = list(base_messages)
        ctx_window = get_context_limit(current_model)
        max_out = (model_params or {}).get("max_tokens", 4096)
        if not isinstance(max_out, int):
            try:
                max_out = int(max_out)
            except (TypeError, ValueError):
                max_out = 4096
        tool_messages = apply_context_budget(tool_messages, ctx_window, max_out, fact_saliences=fact_saliences)
        model_done     = False
        tool_call_counts: dict[str, int] = {}

        for _tool_iter in range(MAX_TOOL_ITERATIONS):
            accumulated      = []
            started          = False
            tool_calls_done  = None
            stream_broke     = False
            nim_usage        = None

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

                    tool_call_counts[fn_name] = tool_call_counts.get(fn_name, 0) + 1
                    if tool_call_counts[fn_name] > 3 and fn_name not in _READONLY_CANVAS_TOOLS:
                        logger.warning("[service] tool_loop_guard: %s called %d times, aborting", fn_name, tool_call_counts[fn_name])
                        yield {"type": "error", "message": f"Tool loop detected: {fn_name} called too many times"}
                        return

                    yield {"type": "tool_call", "name": fn_name, "args": args}
                    result = await execute_tool(fn_name, args, db, user_id, conv_id)

                    if result.startswith(ASK_USER_PREFIX):
                        question = result[len(ASK_USER_PREFIX):]
                        yield {"type": "ask_user", "question": question}
                        done_ev = {"type": "done", "model": current_model, "cache_hit": False, "fallback_used": fallback_used}
                        if nim_usage:
                            done_ev["usage"] = nim_usage
                        yield done_ev
                        ask_user_triggered = True
                        break

                    if result.startswith(CONFIRM_WRITE_PREFIX):
                        fact = result[len(CONFIRM_WRITE_PREFIX):]
                        yield {"type": "confirm_write_memory", "fact": fact}
                        done_ev = {"type": "done", "model": current_model, "cache_hit": False, "fallback_used": fallback_used}
                        if nim_usage:
                            done_ev["usage"] = nim_usage
                        yield done_ev
                        ask_user_triggered = True
                        break

                    yield {"type": "tool_result", "name": fn_name, "content": result[:500]}
                    tool_messages.append({"role": "assistant", "tool_calls": [tc]})
                    tool_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result[:12000]})

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

            done_ev = {"type": "done", "model": current_model, "cache_hit": False, "fallback_used": fallback_used}
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
