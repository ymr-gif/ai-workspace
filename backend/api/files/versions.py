import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import FileVersion, User
from services.file_service import restore_version

from .utils import _get_file_or_404

router = APIRouter()


@router.get("/{file_id}/versions")
async def list_file_versions(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    fid, _ = await _get_file_or_404(file_id, db, current_user.id)
    result = await db.execute(
        select(FileVersion)
        .where(FileVersion.file_id == fid)
        .order_by(FileVersion.version.desc())
        .limit(50)
    )
    return [
        {
            "id":         str(v.id),
            "version":    v.version,
            "created_at": v.created_at.isoformat(),
            "size_chars": len(v.content),
        }
        for v in result.scalars().all()
    ]


@router.get("/{file_id}/versions/{version_id}")
async def get_file_version(
    file_id:      str,
    version_id:   str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    fid, _ = await _get_file_or_404(file_id, db, current_user.id)
    try:
        vid = uuid.UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    v = await db.get(FileVersion, vid)
    if not v or v.file_id != fid:
        raise HTTPException(status_code=404, detail="Not found")
    return {"id": str(v.id), "version": v.version, "content": v.content, "created_at": v.created_at.isoformat()}


@router.post("/{file_id}/versions/{version_id}/restore")
async def restore_file_version(
    file_id:      str,
    version_id:   str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    fid, _ = await _get_file_or_404(file_id, db, current_user.id)
    try:
        vid = uuid.UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    content = await restore_version(db, current_user.id, fid, vid)
    if content is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "size_chars": len(content)}
