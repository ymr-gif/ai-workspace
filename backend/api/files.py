import asyncio
import json as _json
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import File as FileModel, FileChunk, FileVersion, User
from observability.file_metrics import record_delete, record_upload
from services.file_service import patch_content, restore_version, write_content
from services.processor import extract_url_text, process_file_async
from storage.storage_manager import StorageManager

logger  = logging.getLogger("files")
router  = APIRouter()
storage = StorageManager()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _file_dict(f: FileModel) -> dict:
    return {
        "id":           str(f.id),
        "filename":     f.filename,
        "mime_type":    f.mime_type,
        "size_bytes":   f.size_bytes,
        "status":       f.upload_status,
        "workspace_id": f.workspace_id or "",
        "created_at":   f.created_at.isoformat(),
    }


@router.post("/upload", status_code=201)
async def upload_file(
    file:         UploadFile   = File(...),
    workspace_id: str          = Form(""),
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    try:
        storage_path, filename, size_bytes = await storage.save_file(file)

        db_file = FileModel(
            user_id      = current_user.id,
            filename     = filename,
            mime_type    = file.content_type or "application/octet-stream",
            size_bytes   = size_bytes,
            storage_path = storage_path,
            workspace_id = workspace_id.strip() or None,
            upload_status= "uploaded",
        )
        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)

        asyncio.create_task(
            process_file_async(db_file.id, storage_path, db_file.mime_type)
        )
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
    workspace_id: str | None   = None,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    q = select(FileModel).where(FileModel.user_id == current_user.id)
    if workspace_id:
        q = q.where(FileModel.workspace_id == workspace_id)
    q = q.order_by(FileModel.created_at.desc()).limit(200)
    result = await db.execute(q)
    return [_file_dict(f) for f in result.scalars().all()]


@router.get("/{file_id}/content")
async def get_file_content(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        content = Path(f.storage_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read file")

    return {"filename": f.filename, "content": content, "mime_type": f.mime_type}


@router.delete("/{file_id}", status_code=200)
async def delete_file(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    await db.execute(delete(FileChunk).where(FileChunk.file_id == fid))
    await db.delete(f)
    await db.commit()
    record_delete()

    try:
        Path(f.storage_path).unlink(missing_ok=True)
    except Exception:
        pass

    return {"ok": True}


class IngestURLRequest(BaseModel):
    url:          str
    workspace_id: str = ""


@router.post("/ingest-url", status_code=201)
async def ingest_url(
    body:         IngestURLRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    text, title = await extract_url_text(url)
    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from URL")

    safe_title = re.sub(r'[^\w\s-]', '_', title)[:80].strip() or "page"
    storage_path, size_bytes = await storage.save_text(text, f"{safe_title}.txt")

    db_file = FileModel(
        user_id      = current_user.id,
        filename     = (title[:255] or url[:255]).strip(),
        mime_type    = "text/plain",
        size_bytes   = size_bytes,
        storage_path = storage_path,
        workspace_id = body.workspace_id.strip() or None,
        upload_status= "uploaded",
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)

    asyncio.create_task(
        process_file_async(db_file.id, storage_path, "text/plain")
    )

    return _file_dict(db_file)


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


class WorkspacePatch(BaseModel):
    workspace_id: str = ""


@router.patch("/{file_id}/workspace")
async def patch_file_workspace(
    file_id:      str,
    body:         WorkspacePatch,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    f.workspace_id = body.workspace_id.strip() or None
    await db.commit()
    return _file_dict(f)


@router.get("/{file_id}/status")
async def get_file_status(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    return {"id": str(f.id), "status": f.upload_status}


@router.get("/{file_id}/status/stream")
async def stream_file_status(
    file_id:      str,
    request:      Request,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    async def status_events():
        last_status = None
        last_pct    = None
        pkey        = f"proc_progress:{fid}"
        redis = None
        try:
            from core.redis_client import get_redis
            redis = get_redis()
        except Exception:
            pass

        try:
            while True:
                db.expire(f)
                await db.refresh(f)
                status = f.upload_status

                pct = None
                if status == "processing" and redis:
                    try:
                        val = await redis.get(pkey)
                        pct = float(val) if val else None
                    except Exception:
                        redis = None

                if status != last_status or pct != last_pct:
                    last_status = status
                    last_pct    = pct
                    data = {"id": str(fid), "status": status}
                    if pct is not None:
                        data["progress"] = pct
                    yield f"data: {_json.dumps(data)}\n\n"

                if status in ("ready", "error"):
                    break
                await asyncio.sleep(0.8)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        status_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{file_id}/download")
async def download_file(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    p = Path(f.storage_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=str(p),
        filename=f.filename,
        media_type=f.mime_type or "application/octet-stream",
    )


class RenameRequest(BaseModel):
    filename: str


@router.patch("/{file_id}/rename")
async def rename_file(
    file_id:      str,
    body:         RenameRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    new_name = body.filename.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Filename required")
    f.filename = new_name[:512]
    await db.commit()
    return _file_dict(f)


class ContentPatchRequest(BaseModel):
    old_text: str
    new_text: str


@router.put("/{file_id}/content")
async def put_file_content(
    file_id:      str,
    body:         dict,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    content = body.get("content", "")
    result = await write_content(db, current_user.id, fid, content)
    if result.startswith("Error"):
        raise HTTPException(status_code=400, detail=result)
    return {"ok": True, "message": result}


@router.get("/{file_id}/versions")
async def list_file_versions(
    file_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    result = await db.execute(
        select(FileVersion)
        .where(FileVersion.file_id == fid)
        .order_by(FileVersion.version.desc())
        .limit(50)
    )
    versions = result.scalars().all()
    return [
        {
            "id":         str(v.id),
            "version":    v.version,
            "created_at": v.created_at.isoformat(),
            "size_chars": len(v.content),
        }
        for v in versions
    ]


@router.get("/{file_id}/versions/{version_id}")
async def get_file_version(
    file_id:    str,
    version_id: str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
        vid = uuid.UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    v = await db.get(FileVersion, vid)
    if not v or v.file_id != fid:
        raise HTTPException(status_code=404, detail="Not found")
    return {"id": str(v.id), "version": v.version, "content": v.content, "created_at": v.created_at.isoformat()}


@router.post("/{file_id}/versions/{version_id}/restore")
async def restore_file_version(
    file_id:    str,
    version_id: str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        fid = uuid.UUID(file_id)
        vid = uuid.UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    content = await restore_version(db, current_user.id, fid, vid)
    if content is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "size_chars": len(content)}
