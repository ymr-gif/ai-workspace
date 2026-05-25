import asyncio
import json
import logging
import time
import uuid

from config import FALLBACK_ORDER, MODELS
from cache import get_cached_response, set_cached_response
from observability import metrics, observability, events
from llm.router import route
from llm.nim import call, call_stream
from llm.tools import TOOL_SCHEMAS, execute_tool

MAX_TOOL_ITERATIONS = 5

logger = logging.getLogger("service")


def build_context_messages(
    memory_sheet:     str,
    project_summary:  str,
    retrieved_chunks: list[str],
    history_summary:  str,
    history:          list[dict],
    memory_enabled:   bool,
    system_prompt:    str | None   = None,
    file_chunks:      list[str]    = (),
    file_names:       list[str]    = (),
    file_ids:         list         = (),
) -> list[dict]:
    messages = []

    # System prompt — append file notice with IDs if files attached
    if file_names:
        if file_ids:
            files_list  = "\n".join(f"  - {name} (id={fid})" for name, fid in zip(file_names, file_ids))
            file_notice = f"The user has attached these files:\n{files_list}\nUse read_file(file_id=<id>) to read their content. Use write_file to edit. Use list_files if unsure of IDs."
        else:
            file_notice = f"The user has attached these files: {', '.join(file_names)}. Use file tools to read or edit them."
        base = system_prompt.rstrip() + "\n\n" + file_notice if system_prompt else file_notice
        messages.append({"role": "system", "content": base})
    elif system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if memory_enabled:
        if memory_sheet:
            messages.append({"role": "system",    "content": f"[USER STATE]\n{memory_sheet}"})
        if project_summary:
            messages.append({"role": "user",      "content": f"[PROJECT STATE]\n{project_summary}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if retrieved_chunks:
            chunks_text = "\n\n".join(retrieved_chunks)
            messages.append({"role": "user",      "content": f"[RELEVANT CONTEXT FROM EARLIER]\n{chunks_text}"})
            messages.append({"role": "assistant", "content": "Understood."})
        if history_summary:
            messages.append({"role": "user",      "content": f"[EARLIER IN THIS CONVERSATION]\n{history_summary}"})
            messages.append({"role": "assistant", "content": "Understood."})

    messages += history

    # FILE CONTEXT last — right before user message for maximum model attention
    if file_chunks:
        joined = "\n\n---\n\n".join(file_chunks)
        messages.append({"role": "user",      "content": f"[FILE CONTEXT]\n{joined}"})
        messages.append({"role": "assistant", "content": "Understood, I will reference these documents in my response."})

    return messages


async def generate_response(message: str, request_id: str) -> dict:
    total_start = time.monotonic()

    try:
        await observability.publish_request_event(
            events.request_event(request_id=request_id)
        )
    except Exception:
        pass

    cached = await get_cached_response(message)
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
):
    use_cache = not history and not model_override and not model_params and not system_prompt and not file_chunks

    if use_cache:
        cached = await get_cached_response(message)
        if cached:
            yield {"type": "token", "content": cached["response"]}
            yield {"type": "done",  "model": cached.get("model", "cache"), "cache_hit": True, "fallback_used": False}
            return

    # Force 70B when files attached — only 70B reliably supports tool calling
    if file_ids and not model_override:
        fallback_chain = [MODELS["reasoning"]]
    elif model_override:
        fallback_chain = [model_override]
    else:
        model, _ = await route(message, request_id)
        fallback_chain = [model] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != model]

    tools = TOOL_SCHEMAS if (file_ids and db is not None) else None

    base_messages = build_context_messages(
        memory_sheet, project_summary, retrieved_chunks, history_summary,
        history, memory_enabled, system_prompt, file_chunks, file_names, file_ids,
    ) + [{"role": "user", "content": message}]

    for idx, current_model in enumerate(fallback_chain):
        fallback_used  = idx > 0
        tool_messages  = list(base_messages)  # per-model copy, extended by tool results
        model_done     = False

        for _tool_iter in range(MAX_TOOL_ITERATIONS):
            accumulated      = []
            started          = False
            tool_calls_done  = None
            stream_broke     = False

            try:
                async for chunk in call_stream(current_model, tool_messages, request_id, model_params, tools):
                    if isinstance(chunk, dict) and "__tool_calls__" in chunk:
                        tool_calls_done = chunk["__tool_calls__"]
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
                for tc in tool_calls_done:
                    fn_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}
                    yield {"type": "tool_call", "name": fn_name, "args": args}
                    result = await execute_tool(fn_name, args, db, user_id, conv_id)
                    yield {"type": "tool_result", "name": fn_name, "content": result[:500]}
                    tool_messages.append({"role": "assistant", "tool_calls": [tc]})
                    tool_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                continue  # next tool iteration

            if not accumulated:
                logger.warning("[service] empty_stream model=%s", current_model)
                break  # try next fallback model

            full_response = "".join(accumulated)
            payload = {
                "response":      full_response,
                "model":         current_model,
                "cache_hit":     False,
                "fallback_used": fallback_used,
            }
            if use_cache:
                try:
                    await set_cached_response(message, payload)
                    metrics.record_cache_write()
                except Exception as e:
                    logger.warning("[cache] write_failed err=%s", e)
            if fallback_used:
                metrics.record_fallback()

            yield {"type": "done", "model": current_model, "cache_hit": False, "fallback_used": fallback_used}
            model_done = True
            break

        else:
            # exhausted MAX_TOOL_ITERATIONS without a text response
            yield {"type": "error", "message": "Tool loop limit reached"}
            return

        if model_done:
            return

    yield {"type": "error", "message": "All models failed"}


async def compare_streams(
    message:      str,
    common_msgs:  list[dict],
    model_params: dict | None,
    request_id:   str,
):
    """Run all models concurrently; yield tagged token events."""
    queue  = asyncio.Queue()
    models = list(MODELS.values())

    async def _run(model: str) -> None:
        try:
            msgs = common_msgs + [{"role": "user", "content": message}]
            async for chunk in call_stream(model, msgs, request_id, model_params):
                await queue.put({"type": "token", "content": chunk, "model": model})
        except Exception as e:
            logger.warning("[compare] %s failed: %s", model, e)
        await queue.put({"__done__": model})

    tasks = [asyncio.create_task(_run(m)) for m in models]
    done  = 0

    while done < len(models):
        item = await queue.get()
        if "__done__" in item:
            done += 1
        else:
            yield item

    yield {"type": "done", "compare": True, "model": "compare", "cache_hit": False, "fallback_used": False}
    await asyncio.gather(*tasks, return_exceptions=True)
