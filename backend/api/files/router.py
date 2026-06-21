import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import File as FileModel, FileChunk, User
from observability.file_metrics import record_delete, record_upload
from rate_limiter import limit
from services.file_service import write_content
from services.processor import process_file_async

from .utils import MAX_FILE_SIZE, _file_dict, _get_file_or_404, logger, storage

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_file(
    file:         UploadFile   = File(...),
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
    _:            None         = limit(20, 60, "upload"),
):
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    try:
        storage_path, filename, size_bytes, sha256 = await storage.save_file(file)

        existing = await db.scalar(
            select(FileModel).where(
                FileModel.user_id == current_user.id,
                FileModel.sha256_hash == sha256,
            )
        )
        if existing:
            Path(storage_path).unlink(missing_ok=True)
            result = _file_dict(existing)
            result["duplicate"] = True
            return result

        mt = file.content_type or "application/octet-stream"
        db_file = FileModel(
            user_id      = current_user.id,
            filename     = filename,
            mime_type    = mt,
            size_bytes   = size_bytes,
            storage_path = storage_path,
            upload_status= "uploaded",
            sha256_hash  = sha256,
            media_type   = "image" if mt.startswith("image/") else "document",
        )
        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)

        asyncio.create_task(process_file_async(db_file.id, storage_path, db_file.mime_type))
        record_upload()
        return _file_dict(db_file)

    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("[files] upload failed user=%s", current_user.username)
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("")
async def list_files(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    q = select(FileModel).where(FileModel.user_id == current_user.id)
    q = q.order_by(FileModel.created_at.desc()).limit(200)
    result = await db.execute(q)
    return [_file_dict(f) for f in result.scalars().all()]


@router.delete("/{file_id}", status_code=200)
async def delete_file(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    fid, f = await _get_file_or_404(file_id, db, current_user.id)
    await db.execute(delete(FileChunk).where(FileChunk.file_id == fid))
    await db.delete(f)
    await db.commit()
    record_delete()
    try:
        Path(f.storage_path).unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True}


@router.get("/{file_id}/content")
async def get_file_content(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    _, f = await _get_file_or_404(file_id, db, current_user.id)
    try:
        content = Path(f.storage_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read file")
    return {"filename": f.filename, "content": content, "mime_type": f.mime_type}


@router.get("/{file_id}/status")
async def get_file_status(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    fid, f = await _get_file_or_404(file_id, db, current_user.id)
    return {"id": str(fid), "status": f.upload_status}


@router.get("/{file_id}/download")
async def download_file(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    _, f = await _get_file_or_404(file_id, db, current_user.id)
    p = Path(f.storage_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(path=str(p), filename=f.filename, media_type=f.mime_type or "application/octet-stream")


class RenameRequest(BaseModel):
    filename: str


@router.patch("/{file_id}/rename")
async def rename_file(
    file_id:      str,
    body:         RenameRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    _, f = await _get_file_or_404(file_id, db, current_user.id)
    new_name = body.filename.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Filename required")
    f.filename = new_name[:512]
    await db.commit()
    return _file_dict(f)


@router.put("/{file_id}/content")
async def put_file_content(
    file_id:      str,
    body:         dict,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    fid, _ = await _get_file_or_404(file_id, db, current_user.id)
    content = body.get("content", "")
    result  = await write_content(db, current_user.id, fid, content)
    if result.startswith("Error"):
        raise HTTPException(status_code=400, detail=result)
    return {"ok": True, "message": result}
