import logging
import time

from config import FALLBACK_ORDER, MODELS
from cache import get_cached_response, set_cached_response
from observability import metrics, observability, events
from llm.router import route
from llm.nim import call, call_stream

logger = logging.getLogger("service")


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
    memory_enabled:   bool = True,
):
    use_cache = not history

    if use_cache:
        cached = await get_cached_response(message)
        if cached:
            yield {"type": "token", "content": cached["response"]}
            yield {"type": "done",  "model": cached.get("model", "cache"), "cache_hit": True, "fallback_used": False}
            return

    model, _ = await route(message, request_id)
    fallback_chain = [model] + [MODELS[k] for k in FALLBACK_ORDER if MODELS[k] != model]

    messages = []
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
    messages += history + [{"role": "user", "content": message}]

    for idx, current_model in enumerate(fallback_chain):
        fallback_used = idx > 0
        accumulated   = []
        started       = False

        try:
            async for chunk in call_stream(current_model, messages, request_id):
                started = True
                accumulated.append(chunk)
                yield {"type": "token", "content": chunk}

            if not accumulated:
                logger.warning("[service] empty_stream model=%s", current_model)
                continue

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
            return

        except Exception as e:
            logger.warning("[service] stream_failed model=%s started=%s err=%s", current_model, started, e)
            if started:
                yield {"type": "error", "message": "Stream interrupted"}
                return
            continue

    yield {"type": "error", "message": "All models failed"}
