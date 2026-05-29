import asyncio
import logging
import uuid

from config import MODEL_PRICING, MODELS
from llm import retriever
from llm.embeddings import embed as embed_text
from models import Conversation

from .helpers import _estimate_tokens
from .schemas import ChatRequest

logger = logging.getLogger("chat")


async def _embed_exchange(
    message_id:      uuid.UUID,
    conversation_id: uuid.UUID,
    user_text:       str,
    assistant_text:  str,
) -> None:
    for attempt in range(2):
        try:
            exchange = f"{user_text[:300]}\n{assistant_text[:400]}"
            emb = await embed_text(exchange, input_type="passage")
            if emb:
                await retriever.store_exchange(message_id, conversation_id, user_text, assistant_text, emb)
            return
        except Exception:
            if attempt == 0:
                logger.warning("[embed_exchange] retry msg=%s", message_id)
            else:
                logger.exception("[embed_exchange] failed msg=%s", message_id)


async def _generate_proactive(user_msg: str, ai_msg: str) -> str | None:
    from llm.agency import generate_proactive_suggestion
    try:
        return await generate_proactive_suggestion(user_msg, ai_msg)
    except Exception:
        logger.exception("[proactive] failed")
        return None


async def _auto_title(conv_id: uuid.UUID, user_msg: str, ai_msg: str) -> None:
    from sqlalchemy import update
    from core.db import AsyncSessionLocal
    from llm.nim import call
    prompt = (
        f"Summarize this exchange in 6 words or fewer:\n"
        f"User: {user_msg[:200]}\nAI: {ai_msg[:200]}"
    )
    try:
        result = await call(
            model      = MODELS["llama"],
            messages   = [{"role": "user", "content": prompt}],
            request_id = f"title-{conv_id}",
        )
        title = (result.get("content") or "").strip().strip('"').strip("'")
        if title and len(title) <= 80:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Conversation)
                    .where(
                        Conversation.id    == conv_id,
                        Conversation.title == user_msg[:60].strip(),
                    )
                    .values(title=title)
                )
                await db.commit()
    except Exception:
        logger.exception("[auto_title] failed conv=%s", conv_id)


def _calculate_tokens_and_cost(
    event:         dict,
    ctx:           dict,
    req:           ChatRequest,
    full_response: str,
    model_used:    str,
) -> tuple[int, int, int, float]:
    pricing = MODEL_PRICING.get(model_used, {})
    nim_usage = event.get("usage")
    if nim_usage and isinstance(nim_usage, dict):
        prompt_tokens     = nim_usage.get("prompt_tokens", 0)
        completion_tokens = nim_usage.get("completion_tokens", 0)
        total_tokens      = nim_usage.get("total_tokens", prompt_tokens + completion_tokens)
    else:
        prompt_tokens     = _estimate_tokens(
            ctx["memory_sheet"], ctx["project_summary"],
            ctx["history_summary"],
            *[m["content"] for m in ctx["history"]],
            req.message,
        )
        completion_tokens = len(full_response) // 4
        total_tokens      = prompt_tokens + completion_tokens
    cost_usd = (
        prompt_tokens     / 1_000_000 * pricing.get("input",  0.0) +
        completion_tokens / 1_000_000 * pricing.get("output", 0.0)
    )
    return prompt_tokens, completion_tokens, total_tokens, cost_usd
