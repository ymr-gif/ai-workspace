from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from core.arq_pool import get_arq_pool
from core.db import get_db
from models import User, UserMemory, UserMemoryVersion

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryUpdate(BaseModel):
    content:         str = ""
    project_summary: str = ""


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

@router.get("")
async def get_memory(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    row = await db.get(UserMemory, current_user.id)
    if not row:
        return {"content": "", "project_summary": "", "version": 0, "updated_at": None}
    return {
        "content":         row.content         or "",
        "project_summary": row.project_summary or "",
        "version":         row.version,
        "updated_at":      row.updated_at.isoformat() if row.updated_at else None,
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
