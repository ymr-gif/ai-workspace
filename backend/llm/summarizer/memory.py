import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from core.db import AsyncSessionLocal
from models import Conversation, Message, UserMemory, UserMemoryVersion, WorkspaceMemory
from llm.nim import call
from .prompts import _MEMORY_SYSTEM, _NO_UPDATE

logger = logging.getLogger("summarizer")

_MODEL = MODELS["llama"]


async def get_memory(db: AsyncSession, user_id: int) -> str:
    row = await db.get(UserMemory, user_id)
    return row.content if row and row.content else ""


async def update_memory(user_id: int, conversation_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await _update_memory(db, user_id, conversation_id)
        except Exception:
            logger.exception("[summarizer] update_memory failed user_id=%s", user_id)


async def _update_memory(db: AsyncSession, user_id: int, conversation_id: uuid.UUID) -> None:
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": user_id})
    row     = await db.get(UserMemory, user_id)
    last_at = row.last_summarized_at if row else None
    current = row.content if row else ""

    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    if last_at:
        query = query.where(Message.created_at > last_at)

    result       = await db.execute(query)
    new_messages = result.scalars().all()

    if not new_messages:
        return

    exchanges = "\n".join(
        f"{m.role.capitalize()}: {m.content[:400]}"
        for m in new_messages
    )

    prompt = f"""\
Current memory sheet:
{current if current else "(empty)"}

New exchanges to process:
{exchanges}

Update the memory sheet. Reply with the full updated sheet or {_NO_UPDATE}.\
"""

    result = await call(
        model      = _MODEL,
        messages   = [
            {"role": "system", "content": _MEMORY_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        request_id = f"mem-{user_id}",
    )

    if not result.get("ok"):
        logger.warning("[summarizer] nim failed user_id=%s err=%s", user_id, result.get("error"))
        return

    updated = (result.get("content") or "").strip()
    if not updated or updated == _NO_UPDATE:
        return

    words = updated.split()
    if len(words) > 500:
        updated = " ".join(words[:500])

    now = datetime.now(timezone.utc)

    if row:
        db.add(UserMemoryVersion(
            user_id         = user_id,
            version         = row.version,
            content         = row.content         or "",
            project_summary = row.project_summary or "",
        ))
        row.content            = updated
        row.version           += 1
        row.updated_at         = now
        row.last_summarized_at = now
    else:
        db.add(UserMemory(
            user_id            = user_id,
            content            = updated,
            version            = 1,
            updated_at         = now,
            last_summarized_at = now,
        ))

    await db.commit()
    logger.info("[summarizer] memory updated user_id=%s", user_id)

    conv = await db.get(Conversation, conversation_id)
    if conv and conv.workspace_id:
        await _update_workspace_memory(db, conv.workspace_id, exchanges)


async def _update_workspace_memory(db: AsyncSession, workspace_id: uuid.UUID, exchanges: str) -> None:
    result = await db.execute(
        select(WorkspaceMemory).where(WorkspaceMemory.workspace_id == workspace_id)
    )
    ws_mem  = result.scalar_one_or_none()
    current = ws_mem.content if ws_mem and ws_mem.content else ""

    prompt = f"""\
Current workspace memory:
{current if current else "(empty)"}

New exchanges:
{exchanges}

Update the workspace memory with relevant workspace-level context. Reply with the full updated sheet or {_NO_UPDATE}.\
"""

    res = await call(
        model      = _MODEL,
        messages   = [
            {"role": "system", "content": _MEMORY_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        request_id = f"ws-mem-{workspace_id}",
    )

    if not res.get("ok"):
        return

    updated = (res.get("content") or "").strip()
    if not updated or updated == _NO_UPDATE:
        return

    words = updated.split()
    if len(words) > 500:
        updated = " ".join(words[:500])

    now = datetime.now(timezone.utc)
    if ws_mem:
        ws_mem.content    = updated
        ws_mem.version   += 1
        ws_mem.updated_at = now
    else:
        db.add(WorkspaceMemory(workspace_id=workspace_id, content=updated, version=1, updated_at=now))

    await db.commit()
    logger.info("[summarizer] workspace memory updated ws=%s", workspace_id)
