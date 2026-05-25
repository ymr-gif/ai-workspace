from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import File as FileModel, User

from .utils import _file_dict, _get_file_or_404

router = APIRouter()


class WorkspacePatch(BaseModel):
    workspace_id: str = ""


@router.get("/workspaces")
async def list_workspaces(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(distinct(FileModel.workspace_id))
        .where(FileModel.user_id == current_user.id)
        .where(FileModel.workspace_id.isnot(None))
    )
    return {"workspaces": [r for r in result.scalars().all() if r]}


@router.patch("/{file_id}/workspace")
async def patch_file_workspace(
    file_id:      str,
    body:         WorkspacePatch,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    _, f = await _get_file_or_404(file_id, db, current_user.id)
    f.workspace_id = body.workspace_id.strip() or None
    await db.commit()
    return _file_dict(f)
