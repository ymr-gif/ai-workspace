import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from core.db import AsyncSessionLocal
from models import Conversation, Message
from llm.nim import call
from .prompts import _COMPRESS_SYSTEM

logger = logging.getLogger("summarizer")

_MODEL = MODELS["llama"]


async def compress_history(conversation_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await _compress_history(db, conversation_id)
        except Exception:
            logger.exception("[summarizer] compress_history failed conv=%s", conversation_id)


async def _compress_history(db: AsyncSession, conversation_id: uuid.UUID) -> None:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    all_msgs = result.scalars().all()

    if len(all_msgs) <= 10:
        return

    old_msgs = all_msgs[:-10]
    text     = "\n".join(f"{m.role}: {m.content[:400]}" for m in old_msgs)

    result = await call(
        model      = _MODEL,
        messages   = [
            {"role": "system", "content": _COMPRESS_SYSTEM},
            {"role": "user",   "content": text},
        ],
        request_id = f"compress-{conversation_id}",
    )

    if not result.get("ok"):
        logger.warning("[summarizer] compress failed conv=%s err=%s", conversation_id, result.get("error"))
        return

    summary = (result.get("content") or "").strip()
    words   = summary.split()
    if len(words) > 500:
        summary = " ".join(words[:500])

    conv = await db.get(Conversation, conversation_id)
    if conv:
        conv.history_summary = summary
        await db.commit()
        logger.info("[summarizer] history compressed conv=%s old_msgs=%s", conversation_id, len(old_msgs))
