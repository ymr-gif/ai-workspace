import asyncio
import json
import logging
import time

import httpx

from config import NVIDIA_API_KEY, NIM_URL, MAX_RETRIES
import llm.client as llm_client
from llm.circuit_breaker import is_open, record_failure, record_success

logger = logging.getLogger("nim")


async def call(model: str, messages: list[dict], request_id: str) -> dict:
    if llm_client.client is None:
        raise RuntimeError("HTTP client not initialized")
    if not NVIDIA_API_KEY:
        raise RuntimeError("Missing NVIDIA_API_KEY")

    if is_open(model):
        return {"ok": False, "error": "circuit_open", "content": None, "latency_ms": 0, "model": model}

    start = time.monotonic()

    async with llm_client.semaphore:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await llm_client.client.post(
                    NIM_URL,
                    headers={
                        "Authorization": f"Bearer {NVIDIA_API_KEY}",
                        "Content-Type":  "application/json",
                    },
                    json={"model": model, "messages": messages},
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

                data    = response.json()
                content = _extract(data)

                logger.info({"event": "nim_raw_response", "request_id": request_id, "model": model})

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
                        "latency_ms": (time.monotonic() - start) * 1000,
                        "model":      model,
                    }

                record_success(model)
                return {
                    "ok":         True,
                    "error":      None,
                    "content":    content.strip(),
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

            await asyncio.sleep(0.5 * (attempt + 1))

    return {"ok": False, "error": "failed", "content": None,
            "latency_ms": (time.monotonic() - start) * 1000, "model": model}


async def call_stream(model: str, messages: list[dict], request_id: str):
    if llm_client.client is None:
        raise RuntimeError("HTTP client not initialized")
    if not NVIDIA_API_KEY:
        raise RuntimeError("Missing NVIDIA_API_KEY")
    if is_open(model):
        raise RuntimeError("circuit_open")

    async with llm_client.semaphore:
        try:
            async with llm_client.client.stream(
                "POST",
                NIM_URL,
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={"model": model, "messages": messages, "stream": True},
            ) as response:
                if response.status_code != 200:
                    logger.warning("[nim] stream_error model=%s status=%s", model, response.status_code)
                    await record_failure(model)
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        chunk   = json.loads(raw)
                        content = chunk["choices"][0]["delta"].get("content") or ""
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

                record_success(model)

        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning("[nim] stream_network_error model=%s err=%s", model, e)
            await record_failure(model)
            raise


def _extract(data: dict) -> str | None:
    try:
        choices = data.get("choices")
        if choices and isinstance(choices, list):
            first   = choices[0]
            message = first.get("message", {})
            content = message.get("content")

            if isinstance(content, str) and content.strip():
                return content.strip()

            if isinstance(content, list) and content:
                part = content[0]
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()

            delta = first.get("delta", {})
            delta_content = delta.get("content")
            if isinstance(delta_content, str) and delta_content.strip():
                return delta_content.strip()

        text = data.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

    except Exception as e:
        logger.exception("[extract] failed err=%s", e)

    return None
