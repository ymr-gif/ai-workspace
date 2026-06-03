import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import File as FileModel, User
from rate_limiter import limit
from services.processor import extract_url_text, process_file_async

from .utils import _file_dict, storage

router = APIRouter()


class IngestURLRequest(BaseModel):
    url:          str


@router.post("/ingest-url", status_code=201)
async def ingest_url(
    body:         IngestURLRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
    _:            None         = limit(10, 60, "ingest_url"),
):
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    text, title = await extract_url_text(url)
    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from URL")

    safe_title = re.sub(r'[^\w\s-]', '_', title)[:80].strip() or "page"
    storage_path, size_bytes, sha256 = await storage.save_text(text, f"{safe_title}.txt")

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

    db_file = FileModel(
        user_id      = current_user.id,
        filename     = (title[:255] or url[:255]).strip(),
        mime_type    = "text/plain",
        size_bytes   = size_bytes,
        storage_path = storage_path,
        upload_status= "uploaded",
        sha256_hash  = sha256,
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)

    asyncio.create_task(process_file_async(db_file.id, storage_path, "text/plain"))
    return _file_dict(db_file)
