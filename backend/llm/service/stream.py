import json
import logging
import time
import uuid

from config import FALLBACK_ORDER, MODEL_VISION, MODELS
from cache import get_cached_response, set_cached_response
from observability import metrics, observability, events
from llm.router import route, get_context_limit
from llm.nim import call, call_stream
from llm.tools import TOOL_SCHEMAS, execute_tool, ASK_USER_PREFIX

from .context import build_context_messages, _needs_file_tools, apply_context_budget

MAX_TOOL_ITERATIONS = 10

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
    memory_enabled:   bool              = True,
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
    workspace_memory: str               = "",
    graph_context:    str               = "",
    graph_facts:      str               = "",
    conflicted_facts: frozenset         = frozenset(),
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

    # Model selection priority: image → explicit override → file tools → router
    if image_b64:
        fallback_chain = [MODEL_VISION]
    elif model_override:
        fallback_chain = [model_override]
    elif file_ids and _needs_file_tools(message):
        fallback_chain = [MODELS["reasoning"]]
    else:
        model, _ = await route(message, request_id)
        fallback_chain = [model] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != model]

    tools = TOOL_SCHEMAS if (file_ids and db is not None and _needs_file_tools(message)) else None

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
        history, memory_enabled, system_prompt, file_chunks, file_names, file_ids,
        workspace_memory=workspace_memory, graph_context=graph_context,
        graph_facts=graph_facts, conflicted_facts=conflicted_facts,
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
        tool_messages = apply_context_budget(tool_messages, ctx_window, max_out)
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
                    if tool_call_counts[fn_name] > 3:
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

                    yield {"type": "tool_result", "name": fn_name, "content": result[:500]}
                    tool_messages.append({"role": "assistant", "tool_calls": [tc]})
                    tool_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

                if ask_user_triggered:
                    return

                tool_messages = apply_context_budget(tool_messages, ctx_window, max_out)
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
