import asyncio
import json
import logging
import random
import time

import httpx

import config
from config import MAX_RETRIES
import llm.client as llm_client
from llm.circuit_breaker import is_open, record_failure, record_success

logger = logging.getLogger("nim")


def _auth_headers() -> dict:
    """Auth header only when a key is set — the LAN llama.cpp server needs none."""
    headers = {"Content-Type": "application/json"}
    if config.NVIDIA_API_KEY:
        headers["Authorization"] = f"Bearer {config.NVIDIA_API_KEY}"
    return headers


async def call(
    model:        str,
    messages:     list[dict],
    request_id:   str,
    model_params: dict | None  = None,
    tools:        list | None  = None,
) -> dict:
    if llm_client.client is None:
        raise RuntimeError("HTTP client not initialized")
    if not config.NVIDIA_API_KEY and config.LLM_BACKEND != "homeserver":
        raise RuntimeError("Missing NVIDIA_API_KEY")

    if is_open(model):
        return {"ok": False, "error": "circuit_open", "content": None, "tool_calls": None, "latency_ms": 0, "model": model}

    start = time.monotonic()
    body  = {"model": model, "messages": messages, **(model_params or {})}
    if tools:
        body["tools"]       = tools
        body["tool_choice"] = "auto"

    async with llm_client.semaphore:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await llm_client.client.post(
                    config.NIM_URL,
                    headers=_auth_headers(),
                    json=body,
                )

                if response.status_code != 200:
                    logger.warning({
                        "event":         "nim_http_error",
                        "request_id":    request_id,
                        "model":         model,
                        "status_code":   response.status_code,
                        "response_text": response.text,
                        "attempt":       attempt,
                    })
                    if response.status_code >= 500:
                        await record_failure(model)
                        continue
                    return {
                        "ok":         False,
                        "error":      f"http_{response.status_code}",
                        "content":    None,
                        "latency_ms": (time.monotonic() - start) * 1000,
                        "model":      model,
                    }

                data               = response.json()
                content, tool_calls = _extract(data)
                usage              = data.get("usage")  # real token counts from NIM

                logger.info({"event": "nim_raw_response", "request_id": request_id, "model": model})

                if tool_calls:
                    record_success(model)
                    return {
                        "ok":         True,
                        "error":      None,
                        "content":    None,
                        "tool_calls": tool_calls,
                        "usage":      usage,
                        "latency_ms": (time.monotonic() - start) * 1000,
                        "model":      model,
                    }

                if not isinstance(content, str) or not content.strip():
                    logger.warning({
                        "event":             "nim_empty_content",
                        "request_id":        request_id,
                        "model":             model,
                        "extracted_content": content,
                    })
                    await record_failure(model)
                    return {
                        "ok":         False,
                        "error":      "bad_format",
                        "content":    None,
                        "tool_calls": None,
                        "usage":      None,
                        "latency_ms": (time.monotonic() - start) * 1000,
                        "model":      model,
                    }

                record_success(model)
                return {
                    "ok":         True,
                    "error":      None,
                    "content":    content.strip(),
                    "tool_calls": None,
                    "usage":      usage,
                    "latency_ms": (time.monotonic() - start) * 1000,
                    "model":      model,
                }

            except (httpx.TimeoutException, httpx.RequestError) as e:
                logger.warning({
                    "event":      "nim_network_error",
                    "request_id": request_id,
                    "model":      model,
                    "attempt":    attempt,
                    "error":      str(e),
                })
                await record_failure(model)

            except Exception as e:
                logger.exception("[nim] unexpected request_id=%s model=%s err=%s", request_id, model, e)
                await record_failure(model)

            await asyncio.sleep(min(30, 2 ** attempt) * (0.75 + 0.5 * random.random()))

    return {"ok": False, "error": "failed", "content": None, "tool_calls": None,
            "latency_ms": (time.monotonic() - start) * 1000, "model": model}


async def call_stream(
    model:        str,
    messages:     list[dict],
    request_id:   str,
    model_params: dict | None = None,
    tools:        list | None = None,
):
    if llm_client.client is None:
        raise RuntimeError("HTTP client not initialized")
    if not config.NVIDIA_API_KEY and config.LLM_BACKEND != "homeserver":
        raise RuntimeError("Missing NVIDIA_API_KEY")
    if is_open(model):
        raise RuntimeError("circuit_open")

    body = {"model": model, "messages": messages, "stream": True,
            "stream_options": {"include_usage": True}, **(model_params or {})}
    if tools:
        body["tools"]       = tools
        body["tool_choice"] = "auto"

    async with llm_client.semaphore:
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with llm_client.client.stream(
                    "POST",
                    config.NIM_URL,
                    headers=_auth_headers(),
                    json=body,
                ) as response:
                    if response.status_code != 200:
                        logger.warning("[nim] stream_error model=%s status=%s attempt=%d",
                                       model, response.status_code, attempt)
                        # transient throttle / unavailable → backoff + retry before giving up
                        if response.status_code in (429, 503) and attempt < MAX_RETRIES:
                            delay = min(30, 2 ** attempt) * (0.75 + 0.5 * random.random())
                            await asyncio.sleep(delay)
                            continue
                        await record_failure(model)
                        return

                    pending: dict[int, dict] = {}  # index → {id, name, arguments}

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            chunk         = json.loads(raw)

                            # Usage-only chunk (stream_options.include_usage)
                            usage = chunk.get("usage")
                            if usage and isinstance(usage, dict) and not chunk.get("choices"):
                                yield {"__usage__": usage}
                                continue

                            choice        = chunk["choices"][0]
                            delta         = choice.get("delta") or {}
                            finish_reason = choice.get("finish_reason")

                            # Emit usage if attached to the final choice chunk
                            if usage and isinstance(usage, dict):
                                yield {"__usage__": usage}

                            content = delta.get("content") or ""
                            if content:
                                yield content

                            # NB: some models emit `"tool_calls": null` in the delta —
                            # `.get(..., [])` would return None, so coerce with `or []`.
                            for tc in (delta.get("tool_calls") or []):
                                idx = tc.get("index", 0)
                                if idx not in pending:
                                    pending[idx] = {"id": "", "name": "", "arguments": ""}
                                if tc.get("id"):
                                    pending[idx]["id"] = tc["id"]
                                fn = tc.get("function", {})
                                if fn.get("name"):
                                    pending[idx]["name"] += fn["name"]
                                if fn.get("arguments"):
                                    pending[idx]["arguments"] += fn["arguments"]

                            if finish_reason == "tool_calls" and pending:
                                tool_calls = []
                                for i in sorted(pending):
                                    p = pending[i]
                                    tool_calls.append({
                                        "id":   p["id"],
                                        "type": "function",
                                        "function": {
                                            "name":      p["name"],
                                            "arguments": p["arguments"],
                                        },
                                    })
                                yield {"__tool_calls__": tool_calls}

                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            continue

                    record_success(model)
                    return

            except (httpx.TimeoutException, httpx.RequestError) as e:
                logger.warning("[nim] stream_network_error model=%s err=%s attempt=%d", model, e, attempt)
                if attempt < MAX_RETRIES:
                    delay = min(30, 2 ** attempt) * (0.75 + 0.5 * random.random())
                    await asyncio.sleep(delay)
                    continue
                await record_failure(model)
                raise


def _extract(data: dict) -> tuple[str | None, list | None]:
    """Returns (content, tool_calls). Exactly one will be non-None on success."""
    try:
        choices = data.get("choices")
        if choices and isinstance(choices, list):
            first   = choices[0]
            message = first.get("message", {})

            tool_calls = message.get("tool_calls")
            if tool_calls:
                return None, tool_calls

            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip(), None

            if isinstance(content, list) and content:
                part = content[0]
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip(), None

            delta = first.get("delta", {})
            delta_content = delta.get("content")
            if isinstance(delta_content, str) and delta_content.strip():
                return delta_content.strip(), None

        text = data.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip(), None

    except Exception as e:
        logger.exception("[extract] failed err=%s", e)

    return None, None
