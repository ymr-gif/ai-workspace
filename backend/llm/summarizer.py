import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from core.db import AsyncSessionLocal
from models import Conversation, Message, UserMemory, UserMemoryVersion, WorkspaceMemory
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

_PROJECT_SYSTEM = """\
You maintain a project-level state summary across multiple conversations.
Output ONLY key:value pairs grouped under four headers.
Every word must carry information — no prose, no filler.

Headers (omit if empty):
[GOALS]   — what is being built, current objectives, milestones
[ARCH]    — architecture decisions, tech stack choices, patterns adopted
[STATUS]  — what works, what's broken, current progress
[PENDING] — known issues, next steps, open questions, blockers

Rules:
- Max 300 words total
- Format each line as: key: value
- Remove anything contradicted by newer info
- If nothing new: reply exactly NO_UPDATE\
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


async def update_project_summary(user_id: int) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await _update_project_summary(db, user_id)
        except Exception:
            logger.exception("[summarizer] update_project_summary failed user_id=%s", user_id)


# ── internals ─────────────────────────────────────────────────────────────────

async def _update_memory(db: AsyncSession, user_id: int, conversation_id: uuid.UUID) -> None:
    # advisory lock prevents concurrent memory updates for the same user
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

    # Also update WorkspaceMemory if conversation belongs to a workspace
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


async def _update_project_summary(db: AsyncSession, user_id: int) -> None:
    # same advisory lock namespace as _update_memory to serialize all memory writes per user
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": user_id})
    # collect last 5 conversation summaries for this user
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
