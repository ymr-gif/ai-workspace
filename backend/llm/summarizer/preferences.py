import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from llm.nim import call
from models import Conversation, Message, UserMemory, UserMemoryVersion

logger = logging.getLogger("summarizer")

_MODEL = MODELS["reasoning"]

_PREF_SYSTEM = """\
You extract user preferences from conversation history.
Output a [PREFERENCES] section with these keys:
- verbosity: how detailed the user wants responses (concise / balanced / detailed)
- tone: preferred tone (professional / casual / technical / instructional)
- domains: comma-separated topics the user works with
- response_style: how they want answers (direct answer / step-by-step / code-first / explanation-first)

Format each line as: key: value
Output ONLY the [PREFERENCES] block. If no clear preferences found, output [PREFERENCES] with "none" for each key.\
"""


async def extract_preferences(user_id: int, db: AsyncSession) -> None:
    msgs_result = await db.execute(
        select(Message.content, Message.role)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id, Message.role.in_(["user", "assistant"]))
        .order_by(Message.created_at.desc())
        .limit(40)
    )
    rows = msgs_result.all()
    if not rows:
        return

    msgs_text = "\n".join(
        f"{r.role.upper()}: {r.content[:500]}" for r in reversed(rows)
    )

    prompt = f"""\
Recent conversation history:
{msgs_text}

Extract user preferences from the above.\
"""

    result = await call(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _PREF_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        request_id=f"pref-extract-{user_id}",
    )

    if not result.get("ok"):
        logger.warning("[preferences] NIM call failed user_id=%s", user_id)
        return

    content = (result.get("content") or "").strip()
    if not content:
        return

    pref_block = _extract_pref_section(content)
    if not pref_block:
        logger.info("[preferences] no [PREFERENCES] block found user_id=%s", user_id)
        return

    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": user_id})
    row = await db.get(UserMemory, user_id)
    if not row:
        row = UserMemory(user_id=user_id, content="", version=0)
        db.add(row)
        await db.flush()

    current = row.content or ""

    db.add(UserMemoryVersion(
        user_id=user_id,
        version=row.version,
        content=current,
        project_summary=row.project_summary or "",
    ))

    new_content = _replace_or_append_pref(current, pref_block)
    row.content = new_content
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)

    await db.commit()
    logger.info("[preferences] extracted for user_id=%s", user_id)


def _extract_pref_section(text: str) -> str | None:
    m = re.search(r'\[PREFERENCES\](.*?)(?=\[|$)', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _replace_or_append_pref(current: str, pref_block: str) -> str:
    new_pref = f"[PREFERENCES]\n{pref_block}"
    if re.search(r'\[PREFERENCES\]', current):
        return re.sub(
            r'\[PREFERENCES\].*?(?=\[|$)',
            new_pref,
            current,
            count=1,
            flags=re.DOTALL,
        )
    return current.strip() + "\n\n" + new_pref if current.strip() else new_pref
