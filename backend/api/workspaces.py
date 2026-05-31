import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from core.db import get_db
from models import Conversation, File as FileModel, User, Workspace, WorkspaceMemory

logger   = logging.getLogger("workspaces")
router   = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name:          str
    description:   str | None = None
    system_prompt: str | None = None


class WorkspaceUpdate(BaseModel):
    name:          str | None = None
    description:   str | None = None
    system_prompt: str | None = None


class MemoryUpdate(BaseModel):
    content:         str | None = None
    project_summary: str | None = None


async def _get_workspace_or_404(ws_id: str, user: User, db: AsyncSession) -> Workspace:
    try:
        wid = uuid.UUID(ws_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace_id")
    ws = await db.get(Workspace, wid)
    if not ws or ws.user_id != user.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.post("", status_code=201)
async def create_workspace(
    payload:      WorkspaceCreate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    ws = Workspace(
        user_id       = current_user.id,
        name          = payload.name.strip(),
        description   = payload.description,
        system_prompt = payload.system_prompt,
    )
    db.add(ws)
    await db.flush()
    await db.commit()
    await db.refresh(ws)
    logger.info("[workspaces] created id=%s user=%s", ws.id, current_user.username)
    return _ws_dict(ws)


@router.get("")
async def list_workspaces(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace).where(Workspace.user_id == current_user.id).order_by(Workspace.created_at)
    )
    workspaces = result.scalars().all()

    # Attach counts per workspace
    conv_counts = await db.execute(
        select(Conversation.workspace_id, func.count().label("n"))
        .where(Conversation.user_id == current_user.id)
        .group_by(Conversation.workspace_id)
    )
    file_counts = await db.execute(
        select(FileModel.workspace_id, func.count().label("n"))
        .where(FileModel.user_id == current_user.id)
        .group_by(FileModel.workspace_id)
    )
    conv_map = {r.workspace_id: r.n for r in conv_counts}
    file_map = {r.workspace_id: r.n for r in file_counts}

    return [
        {**_ws_dict(ws), "conversation_count": conv_map.get(ws.id, 0), "file_count": file_map.get(ws.id, 0)}
        for ws in workspaces
    ]


@router.get("/{ws_id}")
async def get_workspace(
    ws_id:        str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    return _ws_dict(await _get_workspace_or_404(ws_id, current_user, db))


@router.patch("/{ws_id}")
async def update_workspace(
    ws_id:        str,
    payload:      WorkspaceUpdate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    ws = await _get_workspace_or_404(ws_id, current_user, db)
    if payload.name          is not None: ws.name          = payload.name.strip()
    if payload.description   is not None: ws.description   = payload.description
    if payload.system_prompt is not None: ws.system_prompt = payload.system_prompt
    ws.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ws)
    return _ws_dict(ws)


@router.delete("/{ws_id}", status_code=204)
async def delete_workspace(
    ws_id:        str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    ws = await _get_workspace_or_404(ws_id, current_user, db)
    # Orphan content (SET NULL via FK) happens automatically on delete
    await db.delete(ws)
    await db.commit()
    logger.info("[workspaces] deleted id=%s user=%s", ws_id, current_user.username)


@router.get("/{ws_id}/conversations")
async def list_workspace_conversations(
    ws_id:        str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    await _get_workspace_or_404(ws_id, current_user, db)
    wid = uuid.UUID(ws_id)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.workspace_id == wid, Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return [
        {
            "id":           str(c.id),
            "title":        c.title,
            "memory_enabled": True,
            "locked_model": c.locked_model,
            "updated_at":   c.updated_at.isoformat(),
        }
        for c in convs
    ]


@router.get("/{ws_id}/files")
async def list_workspace_files(
    ws_id:        str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    await _get_workspace_or_404(ws_id, current_user, db)
    wid = uuid.UUID(ws_id)
    result = await db.execute(
        select(FileModel)
        .where(FileModel.workspace_id == wid, FileModel.user_id == current_user.id)
        .order_by(FileModel.created_at.desc())
    )
    files = result.scalars().all()
    return [
        {
            "id":            str(f.id),
            "filename":      f.filename,
            "size_bytes":    f.size_bytes,
            "upload_status": f.upload_status,
            "created_at":    f.created_at.isoformat(),
        }
        for f in files
    ]


@router.get("/{ws_id}/memory")
async def get_workspace_memory(
    ws_id:        str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    ws  = await _get_workspace_or_404(ws_id, current_user, db)
    mem = await _get_or_create_memory(ws.id, db)
    return {
        "content":         mem.content or "",
        "project_summary": mem.project_summary or "",
        "version":         mem.version,
        "updated_at":      mem.updated_at.isoformat(),
    }


@router.put("/{ws_id}/memory")
async def update_workspace_memory(
    ws_id:        str,
    payload:      MemoryUpdate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    ws  = await _get_workspace_or_404(ws_id, current_user, db)
    mem = await _get_or_create_memory(ws.id, db)
    if payload.content         is not None: mem.content         = payload.content
    if payload.project_summary is not None: mem.project_summary = payload.project_summary
    mem.version    += 1
    mem.updated_at  = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(mem)
    return {
        "content":         mem.content or "",
        "project_summary": mem.project_summary or "",
        "version":         mem.version,
        "updated_at":      mem.updated_at.isoformat(),
    }


async def _get_or_create_memory(workspace_id: uuid.UUID, db: AsyncSession) -> WorkspaceMemory:
    result = await db.execute(
        select(WorkspaceMemory).where(WorkspaceMemory.workspace_id == workspace_id)
    )
    mem = result.scalar_one_or_none()
    if not mem:
        mem = WorkspaceMemory(workspace_id=workspace_id)
        db.add(mem)
        await db.flush()
    return mem


def _ws_dict(ws: Workspace) -> dict:
    return {
        "id":           str(ws.id),
        "name":         ws.name,
        "description":  ws.description,
        "system_prompt": ws.system_prompt,
        "created_at":   ws.created_at.isoformat(),
        "updated_at":   ws.updated_at.isoformat(),
    }
