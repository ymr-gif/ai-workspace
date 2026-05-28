import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from core.db import AsyncSessionLocal
from models import UserMemory, UserMemoryVersion
from llm.nim import call
from .prompts import _COMPACT_SYSTEM, _NO_UPDATE

logger = logging.getLogger("summarizer")

_MODEL = MODELS["llama"]


async def compact_memory(user_id: int) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await _compact_memory(db, user_id)
        except Exception:
            logger.exception("[summarizer] compact_memory failed user_id=%s", user_id)


async def _compact_memory(db: AsyncSession, user_id: int) -> None:
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": user_id})
    row = await db.get(UserMemory, user_id)
    if not row or not row.content:
        return

    current = row.content.strip()
    if len(current.split()) < 100:
        logger.info("[summarizer] compact skip user_id=%s too small (%d words)", user_id, len(current.split()))
        return

    prompt = f"""\
Current memory sheet:
{current}

Compact this sheet. Remove stale, duplicate, and low-value information.
Keep high-salience facts only. Output the full compacted sheet or {_NO_UPDATE}.\
"""

    result = await call(
        model      = _MODEL,
        messages   = [
            {"role": "system", "content": _COMPACT_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        request_id = f"compact-{user_id}",
    )

    if not result.get("ok"):
        logger.warning("[summarizer] compact nim failed user_id=%s", user_id)
        return

    updated = (result.get("content") or "").strip()
    if not updated or updated == _NO_UPDATE:
        logger.info("[summarizer] compact noop user_id=%s", user_id)
        return

    words = updated.split()
    if len(words) > 500:
        updated = " ".join(words[:500])

    now = datetime.now(timezone.utc)

    db.add(UserMemoryVersion(
        user_id         = user_id,
        version         = row.version,
        content         = row.content         or "",
        project_summary = row.project_summary or "",
    ))
    row.content  = updated
    row.version += 1
    row.updated_at = now

    await db.commit()
    logger.info("[summarizer] compact done user_id=%s words=%d->%d", user_id, len(current.split()), len(words))
