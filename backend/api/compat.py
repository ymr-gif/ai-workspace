"""OpenAI-compatible /v1/chat/completions endpoint.

Accepts OpenAI request schema, proxies to NIM, returns OpenAI response schema.
Supports both streaming and non-streaming. Auth: JWT or API key.
"""
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import llm.nim as nim
from api.chat.helpers import _check_cost_cap
from api.chat.usage_ledger import record_stateless_usage
from auth.security import get_current_user
from config import MODELS
from core.db import AsyncSessionLocal, get_db
from models import User

router = APIRouter(tags=["compat"])
logger = logging.getLogger("compat")

_MODEL_MAP: dict[str, str] = {
    "gpt-4":         MODELS["reasoning"],
    "gpt-4-turbo":   MODELS["reasoning"],
    "gpt-4o":        MODELS["reasoning"],
    "gpt-4o-mini":   MODELS["llama"],
    "gpt-3.5-turbo": MODELS["llama"],
}


def _resolve_model(model: str) -> str:
    if model in MODELS.values():
        return model
    if model in MODELS:
        return MODELS[model]
    return _MODEL_MAP.get(model, MODELS["llama"])


class ChatMessage(BaseModel):
    role:    str
    content: str


class CompletionRequest(BaseModel):
    model:       str             = "gpt-3.5-turbo"
    messages:    list[ChatMessage]
    stream:      bool            = False
    temperature: float | None   = None
    max_tokens:  int | None     = None
    top_p:       float | None   = None


def _build_params(req: CompletionRequest) -> dict:
    p: dict = {}
    if req.temperature is not None:
        p["temperature"] = req.temperature
    if req.max_tokens is not None:
        p["max_tokens"] = req.max_tokens
    if req.top_p is not None:
        p["top_p"] = req.top_p
    return p


def _completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


@router.post("/v1/chat/completions")
async def chat_completions(
    body:         CompletionRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    # Same cost-cap pre-flight as /chat (49cb6ea) — this endpoint was uncovered (QUEUE Q4).
    await _check_cost_cap(current_user, db)
    model      = _resolve_model(body.model)
    messages   = [{"role": m.role, "content": m.content} for m in body.messages]
    params     = _build_params(body)
    request_id = str(uuid.uuid4())
    cid        = _completion_id()
    created    = int(time.time())
    prompt_text = "\n".join(m["content"] for m in messages)

    if body.stream:
        return StreamingResponse(
            _stream(model, messages, params, request_id, cid, created,
                    user_id=current_user.id, prompt_text=prompt_text),
            media_type="text/event-stream",
        )

    result = await nim.call(model, messages, request_id, model_params=params)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "upstream_error"))

    usage = result.get("usage") or {}
    await record_stateless_usage(
        db, current_user.id, endpoint="/v1/chat/completions", model=model,
        prompt_text=prompt_text, response_text=result.get("content") or "", usage=usage or None,
    )
    return {
        "id":      cid,
        "object":  "chat.completion",
        "created": created,
        "model":   model,
        "choices": [{
            "index":         0,
            "message":       {"role": "assistant", "content": result["content"]},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens":     usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens":      usage.get("total_tokens", 0),
        },
    }


async def _stream(
    model:      str,
    messages:   list[dict],
    params:     dict,
    request_id: str,
    cid:        str,
    created:    int,
    *,
    user_id:     int,
    prompt_text: str,
):
    def _chunk(delta: dict, finish_reason: str | None) -> str:
        payload = {
            "id":      cid,
            "object":  "chat.completion.chunk",
            "created": created,
            "model":   model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    yield _chunk({"role": "assistant"}, None)

    usage: dict | None = None
    parts: list[str] = []
    try:
        async for chunk in nim.call_stream(model, messages, request_id, model_params=params):
            if isinstance(chunk, str):
                parts.append(chunk)
                yield _chunk({"content": chunk}, None)
            elif isinstance(chunk, dict) and "__usage__" in chunk:
                usage = chunk["__usage__"]   # recorded below; not surfaced in compat mode
            # skip __tool_calls__ — not surfaced in compat mode
    except Exception as e:
        logger.warning("[compat] stream error model=%s err=%s", model, e)

    yield _chunk({}, "stop")
    yield "data: [DONE]\n\n"

    # Ledger write with its own session — the request-scoped one may be torn down
    # by the time the StreamingResponse generator finishes.
    if parts or usage:
        async with AsyncSessionLocal() as ledger_db:
            await record_stateless_usage(
                ledger_db, user_id, endpoint="/v1/chat/completions", model=model,
                prompt_text=prompt_text, response_text="".join(parts), usage=usage,
            )
