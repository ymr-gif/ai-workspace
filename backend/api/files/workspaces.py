import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import File as FileModel, User, Workspace

from .utils import _file_dict, _get_file_or_404

router = APIRouter()


class WorkspacePatch(BaseModel):
    workspace_id: str | None = None


@router.get("/workspaces")
async def list_workspaces(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace)
        .where(Workspace.user_id == current_user.id)
        .order_by(Workspace.created_at)
    )
    workspaces = result.scalars().all()
    return {"workspaces": [{"id": str(ws.id), "name": ws.name} for ws in workspaces]}


@router.patch("/{file_id}/workspace")
async def patch_file_workspace(
    file_id:      str,
    body:         WorkspacePatch,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    _, f = await _get_file_or_404(file_id, db, current_user.id)
    if body.workspace_id:
        try:
            wid = uuid.UUID(body.workspace_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid workspace_id")
        ws = await db.get(Workspace, wid)
        if not ws or ws.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Workspace not found")
        f.workspace_id = wid
    else:
        f.workspace_id = None
    await db.commit()
    return _file_dict(f)
