import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from core.db import AsyncSessionLocal
from models import Conversation, UserMemory, UserMemoryVersion
from llm.nim import call
from core.locks import user_write_lock
from .prompts import _NO_UPDATE, _PROJECT_SYSTEM

logger = logging.getLogger("summarizer")

_MODEL = MODELS["llama"]


async def update_project_summary(user_id: int) -> None:
    async with AsyncSessionLocal() as db:
        try:
            async with user_write_lock(db, user_id):
                await _update_project_summary(db, user_id)
        except Exception:
            logger.exception("[summarizer] update_project_summary failed user_id=%s", user_id)


async def _update_project_summary(db: AsyncSession, user_id: int) -> None:
    result = await db.execute(
        select(Conversation.title, Conversation.history_summary)
        .where(
            Conversation.user_id == user_id,
            Conversation.history_summary.isnot(None),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(5)
    )
    convs = result.all()

    if not convs:
        return

    summaries = "\n\n".join(
        f"[{c.title}]\n{c.history_summary}"
        for c in convs
        if c.history_summary
    )

    if not summaries.strip():
        return

    row     = await db.get(UserMemory, user_id)
    current = row.project_summary if row and row.project_summary else ""

    prompt = f"""\
Current project state:
{current if current else "(empty)"}

Recent conversation summaries:
{summaries}

Update the project state. Reply with the full updated state or {_NO_UPDATE}.\
"""

    result = await call(
        model      = _MODEL,
        messages   = [
            {"role": "system", "content": _PROJECT_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        request_id = f"proj-{user_id}",
    )

    if not result.get("ok"):
        logger.warning("[summarizer] project summary failed user_id=%s", user_id)
        return

    updated = (result.get("content") or "").strip()
    if not updated or updated == _NO_UPDATE:
        return

    words = updated.split()
    if len(words) > 300:
        updated = " ".join(words[:300])

    now = datetime.now(timezone.utc)

    if row:
        db.add(UserMemoryVersion(
            user_id         = user_id,
            version         = row.version,
            content         = row.content         or "",
            project_summary = row.project_summary or "",
        ))
        row.project_summary = updated
        row.version        += 1
        row.updated_at      = now
    else:
        db.add(UserMemory(
            user_id         = user_id,
            content         = "",
            project_summary = updated,
            version         = 1,
            updated_at      = now,
        ))

    await db.commit()
    logger.info("[summarizer] project summary updated user_id=%s", user_id)
