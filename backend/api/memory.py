import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from core.arq_pool import get_arq_pool
from core.db import get_db
from llm.summarizer.salience import decay_salience
from llm.summarizer.conflicts import detect_conflicts, resolve_conflict
from llm.summarizer.memory import restructure_memory
from models import MemoryConflict, User, UserMemory, UserMemoryVersion

router = APIRouter(prefix="/memory", tags=["memory"])
logger = logging.getLogger("memory")


class MemoryUpdate(BaseModel):
    content:         str = ""
    project_summary: str = ""


class WriteMemoryBody(BaseModel):
    fact: str


class ResolveBody(BaseModel):
    strategy: str


# ── helpers ───────────────────────────────────────────────────────────────────

def _truncate(text: str, max_words: int) -> str:
    words = text.split()
    return " ".join(words[:max_words]) if len(words) > max_words else text


async def _write_memory(
    body:         MemoryUpdate,
    current_user: User,
    db:           AsyncSession,
) -> dict:
    content         = _truncate(body.content.strip(),         500)
    project_summary = _truncate(body.project_summary.strip(), 300)
    now             = datetime.now(timezone.utc)

    row = await db.scalar(
        select(UserMemory)
        .where(UserMemory.user_id == current_user.id)
        .with_for_update()
    )

    if row:
        db.add(UserMemoryVersion(
            user_id         = current_user.id,
            version         = row.version,
            content         = row.content         or "",
            project_summary = row.project_summary or "",
        ))
        row.content         = content
        row.project_summary = project_summary
        row.version        += 1
        row.updated_at      = now
    else:
        row = UserMemory(
            user_id         = current_user.id,
            content         = content,
            project_summary = project_summary,
            version         = 1,
            updated_at      = now,
        )
        db.add(row)

    await db.commit()
    return {
        "content":         row.content         or "",
        "project_summary": row.project_summary or "",
        "version":         row.version,
        "updated_at":      row.updated_at.isoformat(),
    }


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/write")
async def write_memory_fact(
    body:         WriteMemoryBody,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    fact = body.fact.strip()[:500]
    now  = datetime.now(timezone.utc)

    row = await db.scalar(
        select(UserMemory)
        .where(UserMemory.user_id == current_user.id)
        .with_for_update()
    )

    if row:
        db.add(UserMemoryVersion(
            user_id         = current_user.id,
            version         = row.version,
            content         = row.content         or "",
            project_summary = row.project_summary or "",
        ))
        existing = (row.content or "").strip()
        row.content = (existing + "\n" + fact) if existing else fact
        row.version += 1
        row.salience = (row.salience or 0.0) + 0.1
        row.updated_at = now
    else:
        row = UserMemory(
            user_id         = current_user.id,
            content         = fact,
            version         = 1,
            salience        = 0.1,
            updated_at      = now,
        )
        db.add(row)

    await db.commit()
    asyncio.create_task(restructure_memory(current_user.id))
    return {"status": "ok", "fact": fact}


@router.get("")
async def get_memory(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    row = await db.get(UserMemory, current_user.id)
    now = datetime.now(timezone.utc)

    active_conflicts_result = await db.execute(
        select(MemoryConflict).where(
            MemoryConflict.user_id    == current_user.id,
            MemoryConflict.resolution == "unresolved",
            (MemoryConflict.expires_at == None) | (MemoryConflict.expires_at > now),
        )
    )
    active_conflicts = len(active_conflicts_result.scalars().all())

    if not row:
        return {
            "content":          "",
            "project_summary":  "",
            "version":          0,
            "updated_at":       None,
            "salience":         0.0,
            "confidence":       0.0,
            "last_used_at":     None,
            "facts":            [],
            "active_conflicts": active_conflicts,
        }
    facts = [
        {"content": line.strip(), "salience": row.salience, "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None, "confidence": row.confidence}
        for line in (row.content or "").split("\n")
        if line.strip()
    ]
    return {
        "content":          row.content         or "",
        "project_summary":  row.project_summary or "",
        "version":          row.version,
        "updated_at":       row.updated_at.isoformat() if row.updated_at else None,
        "salience":         row.salience,
        "confidence":       row.confidence,
        "last_used_at":     row.last_used_at.isoformat() if row.last_used_at else None,
        "facts":            facts,
        "active_conflicts": active_conflicts,
    }


@router.put("")
async def update_memory(
    body:         MemoryUpdate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    return await _write_memory(body, current_user, db)


@router.get("/export")
async def export_memory(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    row  = await db.get(UserMemory, current_user.id)
    data = {
        "content":         row.content         if row else "",
        "project_summary": row.project_summary if row else "",
        "version":         row.version         if row else 0,
        "exported_at":     datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(
        content = data,
        headers = {"Content-Disposition": "attachment; filename=memory.json"},
    )


@router.post("/import")
async def import_memory(
    body:         MemoryUpdate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    return await _write_memory(body, current_user, db)


@router.post("/compact")
async def compact_memory(
    current_user: User = Depends(get_current_user),
):
    pool = get_arq_pool()
    if pool:
        await pool.enqueue_job("compact_memory_job", current_user.id)
        return {"status": "queued"}
    return {"status": "skipped", "reason": "arq pool unavailable"}


@router.post("/decay")
async def decay_memory(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    row = await db.get(UserMemory, current_user.id)
    if not row:
        return {"status": "ok", "salience_before": None, "salience_after": None}
    before = row.salience
    row.salience = decay_salience(row.salience)
    row.last_used_at = None
    await db.commit()
    logger.info("[decay] user_id=%s salience=%.4f->%.4f", current_user.id, before, row.salience)
    return {
        "status":          "ok",
        "salience_before": before,
        "salience_after":  row.salience,
    }


@router.get("/conflicts")
async def list_conflicts(
    resolution:   str         = "unresolved",
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    q = select(MemoryConflict).where(MemoryConflict.user_id == current_user.id)
    if resolution != "all":
        q = q.where(MemoryConflict.resolution == resolution)
    result = await db.execute(q.order_by(MemoryConflict.created_at.desc()))
    rows = result.scalars().all()
    return [
        {
            "id":            str(r.id),
            "fact_a":        r.fact_a,
            "fact_b":        r.fact_b,
            "conflict_type": r.conflict_type,
            "resolution":    r.resolution,
            "created_at":    r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict_endpoint(
    conflict_id:  str,
    body:         ResolveBody,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    try:
        cid = _uuid.UUID(conflict_id)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid conflict_id")
    conflict = await db.get(MemoryConflict, cid)
    if not conflict or conflict.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conflict not found")
    valid = {"keep_a", "keep_b", "merge", "discard_both"}
    if body.strategy not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"strategy must be one of {valid}")
    await resolve_conflict(conflict, body.strategy, db)
    await db.commit()
    return {"status": "ok", "resolution": body.strategy}


@router.post("/conflicts/scan")
async def scan_conflicts(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    mem = await db.get(UserMemory, current_user.id)
    if not mem or not mem.content:
        return {"detected": 0}
    conflicts = await detect_conflicts(mem.content)
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    for c in conflicts:
        db.add(MemoryConflict(
            user_id=current_user.id,
            fact_a=c["fact_a"],
            fact_b=c["fact_b"],
            conflict_type=c["conflict_type"],
            resolution="unresolved",
            expires_at=expires,
        ))
    if conflicts:
        await db.commit()
    return {"detected": len(conflicts)}


@router.get("/history")
async def get_memory_history(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserMemoryVersion)
        .where(UserMemoryVersion.user_id == current_user.id)
        .order_by(UserMemoryVersion.created_at.desc())
        .limit(10)
    )
    versions = result.scalars().all()
    return [
        {
            "version":         v.version,
            "content":         v.content         or "",
            "project_summary": v.project_summary or "",
            "created_at":      v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]
