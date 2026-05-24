import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from core.db import AsyncSessionLocal
from models import Conversation, Message, UserMemory
from llm.nim import call

logger = logging.getLogger("summarizer")

_MODEL     = MODELS["llama"]
_NO_UPDATE = "NO_UPDATE"

# ── prompts ───────────────────────────────────────────────────────────────────

_MEMORY_SYSTEM = """\
You maintain a compact memory sheet for a user. Output ONLY key:value pairs grouped under five headers.
Every word must carry information — no filler, no sentences, no prose.

Headers (omit if empty):
[USER]       — name, role, expertise level, background
[STACK]      — languages, frameworks, tools, infra actively used
[PROJECT]    — what they are building, decisions made, constraints, current state
[CORRECTIONS]— errors AI made that were corrected; preferences user had to repeat
[PATTERNS]   — recurring topics, working style, what they care about

Rules:
- Max 500 words total
- Format each line as: key: value
- Remove anything contradicted by newer info
- Be specific — "Python 3.11 + FastAPI async" not "Python backend"
- If nothing new to add: reply exactly NO_UPDATE\
"""

_COMPRESS_SYSTEM = """\
Compress this conversation excerpt into a dense factual summary.
Focus on: decisions made, problems solved, code written, errors fixed, context established.
Output bullet points or key:value pairs. Max 200 words. No filler, no pleasantries.\
"""


# ── public API ────────────────────────────────────────────────────────────────

async def get_memory(db: AsyncSession, user_id: int) -> str:
    row = await db.get(UserMemory, user_id)
    return row.content if row and row.content else ""


async def update_memory(user_id: int, conversation_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await _update_memory(db, user_id, conversation_id)
        except Exception:
            logger.exception("[summarizer] update_memory failed user_id=%s", user_id)


async def compress_history(conversation_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await _compress_history(db, conversation_id)
        except Exception:
            logger.exception("[summarizer] compress_history failed conv=%s", conversation_id)


# ── internals ─────────────────────────────────────────────────────────────────

async def _update_memory(db: AsyncSession, user_id: int, conversation_id: uuid.UUID) -> None:
    row     = await db.get(UserMemory, user_id)
    last_at = row.last_summarized_at if row else None
    current = row.content if row else ""

    # get all messages since last update
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    if last_at:
        query = query.where(Message.created_at > last_at)

    result      = await db.execute(query)
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
    if len(words) > 200:
        summary = " ".join(words[:200])

    conv = await db.get(Conversation, conversation_id)
    if conv:
        conv.history_summary = summary
        await db.commit()
        logger.info("[summarizer] history compressed conv=%s old_msgs=%s", conversation_id, len(old_msgs))
