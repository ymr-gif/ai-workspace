import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from core.db import AsyncSessionLocal
from models import MemoryConflict, UserMemory, UserMemoryVersion
from llm.nim import call
from core.locks import user_write_lock
from .prompts import _COMPACT_SYSTEM, _NO_UPDATE
from .salience import decay_fact_saliences, decay_salience
from .conflicts import detect_conflicts

logger = logging.getLogger("summarizer")

_MODEL = MODELS["llama"]

_CANVAS_BLOCKLIST = re.compile(
    r'(?i)'
    r'(?:'
    r'\bcanvas\b|'
    r'\bsessions?\b|'
    r'\bnode[s]?\b|'
    r'\bworkspace\b|'
    r'\btopic[s]?\b|'
    r'\bpanel[s]?\b|'
    r'Tool loop detected'
    r')'
)
_ALLOWLIST_SUBSTRINGS = frozenset({
    "node.js", "nodejs", "node version", "node package",
    "session management", "session timeout", "session key", "session token",
    "topic model", "topic modeling",
})


def _prune_canvas_corrections(content: str, max_entries: int = 20) -> str:
    import re

    corr_pos = content.find("[CORRECTIONS]")
    if corr_pos == -1:
        return content

    after_corr = content[corr_pos + len("[CORRECTIONS]"):]

    next_sec = re.search(r'\[[A-Z][A-Z_]+\]', after_corr)
    if next_sec:
        corr_body = after_corr[:next_sec.start()].strip()
        suffix = after_corr[next_sec.start():]
    else:
        corr_body = after_corr.strip()
        suffix = ""

    if not corr_body:
        return content

    body_lines = corr_body.split("\n")

    is_inline = len(body_lines) <= 1 and " - " in corr_body

    if is_inline:
        parts = corr_body.split(" - ")
        descriptor = parts[0]
        raw_entries = parts[1:]
    else:
        descriptor = ""
        raw_entries = []
        for ln in body_lines:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("- "):
                s = s[2:]
            elif s.startswith("-"):
                s = s[1:]
            if not descriptor and not s.startswith("-") and (
                s.endswith(":") or "errors" in s or "corrections" in s or "corrected" in s
            ):
                descriptor = s
                continue
            raw_entries.append(s)

    filtered = []
    pruned = 0
    for entry in raw_entries:
        if _CANVAS_BLOCKLIST.search(entry) and not any(
            a in entry.lower() for a in _ALLOWLIST_SUBSTRINGS
        ):
            pruned += 1
        else:
            filtered.append(entry)

    if pruned == 0:
        return content

    to_keep = filtered[-max_entries:]

    if is_inline:
        if not to_keep:
            new_corr = ""
            result = content[:corr_pos].rstrip() + suffix
        else:
            new_corr = "[CORRECTIONS] " + descriptor + " - " + " - ".join(to_keep)
            result = content[:corr_pos] + new_corr + suffix
    else:
        if not to_keep:
            new_corr = ""
            result = content[:corr_pos].rstrip() + suffix
        else:
            lines = []
            if descriptor:
                lines.append(descriptor)
            for e in to_keep:
                lines.append("- " + e)
            new_corr = "[CORRECTIONS]\n" + "\n".join(lines)
            result = content[:corr_pos] + new_corr + "\n" + suffix

    result = re.sub(r'\n{3,}', "\n\n", result)
    return result


async def compact_memory(user_id: int) -> None:
    lock_key = f"compact:running:{user_id}"
    _locked = False
    try:
        from config import USE_REDIS
        if USE_REDIS:
            from core.redis_client import get_redis
            await get_redis().set(lock_key, "1", ex=300)
            _locked = True
    except Exception:
        pass

    try:
        async with AsyncSessionLocal() as db:
            try:
                async with user_write_lock(db, user_id):
                    await _compact_memory(db, user_id)
            except Exception:
                logger.exception("[summarizer] compact_memory failed user_id=%s", user_id)
    finally:
        if _locked:
            try:
                from core.redis_client import get_redis
                await get_redis().delete(lock_key)
            except Exception:
                pass


async def _compact_memory(db: AsyncSession, user_id: int) -> None:
    row = await db.get(UserMemory, user_id)
    if not row or not row.content:
        return

    current = row.content.strip()
    if len(current.split()) < 100:
        logger.info("[summarizer] compact skip user_id=%s too small (%d words)", user_id, len(current.split()))
        return

    pruned = _prune_canvas_corrections(current)
    if pruned != current:
        row.content = pruned
        current = pruned
        logger.info("[summarizer] pruned Canvas corrections user_id=%s", user_id)

    row.salience = decay_salience(row.salience)
    row.fact_saliences = decay_fact_saliences(row.fact_saliences or {})

    if row.salience < 0.3:
        db.add(UserMemoryVersion(
            user_id         = user_id,
            version         = row.version,
            content         = row.content         or "",
            project_summary = row.project_summary or "",
        ))
        row.content         = ""
        row.project_summary = ""
        row.version        += 1
        row.salience        = 0.0
        row.confidence      = 0.0
        row.fact_saliences  = {}
        row.updated_at      = datetime.now(timezone.utc)
        await db.commit()
        logger.info("[summarizer] compact cleared user_id=%s (salience below 0.3)", user_id)
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
    row.content       = updated
    row.version      += 1
    row.salience      = min(row.salience + 0.1, 2.0)
    row.confidence    = min(row.confidence + 0.05, 1.0)
    row.updated_at    = now

    conflicts = await detect_conflicts(updated)
    for c in conflicts:
        db.add(MemoryConflict(
            user_id=user_id,
            fact_a=c["fact_a"],
            fact_b=c["fact_b"],
            conflict_type=c["conflict_type"],
            resolution="unresolved",
        ))
    if conflicts:
        await db.flush()
    logger.info("[conflicts] user_id=%s detected=%d", user_id, len(conflicts))

    await db.commit()
    logger.info("[summarizer] compact done user_id=%s words=%d->%d salience=%.4f", user_id, len(current.split()), len(words), row.salience)
