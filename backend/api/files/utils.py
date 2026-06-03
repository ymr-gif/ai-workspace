import logging
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import File as FileModel
from storage.storage_manager import StorageManager

logger  = logging.getLogger("files")
storage = StorageManager()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _file_dict(f: FileModel) -> dict:
    return {
        "id":              str(f.id),
        "filename":        f.filename,
        "mime_type":       f.mime_type,
        "size_bytes":      f.size_bytes,
        "status":          f.upload_status,
        "chunk_total":     f.chunk_total,
        "chunk_embedded":  f.chunk_embedded,
        "embed_fail_count": f.embed_fail_count,
        "created_at":      f.created_at.isoformat(),
    }


async def _get_file_or_404(file_id: str, db: AsyncSession, user_id: int) -> tuple[uuid.UUID, FileModel]:
    try:
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    f = await db.get(FileModel, fid)
    if not f or f.user_id != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    return fid, f
