import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import File as FileModel, User
from storage.storage_manager import StorageManager

logger  = logging.getLogger("files")
router  = APIRouter()
storage = StorageManager()


@router.post("/upload", status_code=201)
async def upload_file(
    file:         UploadFile = File(...),
    db:           AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        storage_path, filename, size_bytes = await storage.save_file(file)

        db_file = FileModel(
            user_id=current_user.id,
            filename=filename,
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=size_bytes,
            storage_path=storage_path,
            upload_status="uploaded",
        )

        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)

        return {
            "id":         str(db_file.id),
            "filename":   db_file.filename,
            "size_bytes": db_file.size_bytes,
            "status":     db_file.upload_status,
        }

    except HTTPException:
        raise

    except Exception:
        await db.rollback()
        logger.exception("[files] upload failed user=%s file=%s", current_user.username, file.filename)
        raise HTTPException(status_code=500, detail="Upload failed")
