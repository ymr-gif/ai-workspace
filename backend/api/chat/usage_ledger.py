"""Spend accounting for the stateless chat endpoints (/chat and /v1/chat/completions).

The cost ledger IS `messages` rows — `_check_cost_cap` (helpers.py) and GET /usage both
aggregate Message.cost_usd through the conversation join. The stateless endpoints persist no
conversation, so their spend was invisible to the rolling window (BUGS.md "Stateless chat
endpoints", QUEUE Q4). Rather than a new table + migration, each user's stateless spend is
recorded as assistant-role Message rows in ONE hidden, archived "[API usage]" conversation:
both aggregators then include it automatically.

Never raises to the caller — a ledger failure must not break the chat reply.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from config import MODEL_PRICING
from models import Conversation, Message

logger = logging.getLogger("usage_ledger")

LEDGER_TITLE = "[API usage] stateless endpoints"


def tokens_and_cost(
    usage: dict | None,
    prompt_text: str,
    response_text: str,
    model: str,
) -> tuple[int, int, int, float, bool]:
    """Return (prompt_tokens, completion_tokens, total_tokens, cost_usd, estimated).

    Mirrors background._calculate_tokens_and_cost: NIM usage when present, else the
    4-chars-per-token heuristic (flagged estimated, like migration 032 backfills).
    """
    pricing = MODEL_PRICING.get(model, {})
    if usage and isinstance(usage, dict):
        prompt_tokens     = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens      = usage.get("total_tokens", prompt_tokens + completion_tokens)
        estimated = False
    else:
        prompt_tokens     = len(prompt_text) // 4
        completion_tokens = len(response_text) // 4
        total_tokens      = prompt_tokens + completion_tokens
        estimated = True
    cost_usd = (
        prompt_tokens     / 1_000_000 * pricing.get("input",  0.0) +
        completion_tokens / 1_000_000 * pricing.get("output", 0.0)
    )
    return prompt_tokens, completion_tokens, total_tokens, cost_usd, estimated


async def record_stateless_usage(
    db,
    user_id: int,
    *,
    endpoint: str,
    model: str,
    prompt_text: str,
    response_text: str,
    usage: dict | None,
) -> None:
    """Append one assistant ledger row for a stateless call. Commits; never raises."""
    try:
        pt, ct, tt, cost, estimated = tokens_and_cost(usage, prompt_text, response_text, model)
        conv = (
            await db.execute(
                select(Conversation).where(
                    Conversation.user_id == user_id,
                    Conversation.title == LEDGER_TITLE,
                )
            )
        ).scalars().first()
        if conv is None:
            conv = Conversation(
                user_id=user_id,
                title=LEDGER_TITLE,
                is_archived=True,
                archived_at=datetime.now(timezone.utc),
            )
            db.add(conv)
            await db.flush()
        db.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=f"[{endpoint}] {model}",
                model=model,
                prompt_tokens=pt,
                completion_tokens=ct,
                total_tokens=tt,
                cost_usd=cost,
                token_estimate=estimated or None,
            )
        )
        await db.commit()
    except Exception:
        logger.exception("[usage_ledger] record failed endpoint=%s user=%s", endpoint, user_id)
        try:
            await db.rollback()
        except Exception:
            pass
