"""Shared file mutation logic used by both the API and AI tool loop."""
import asyncio
import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import File as FileModel, FileChunk, FileVersion
from services.processor import process_file_async
from observability.file_metrics import record_tool_call

logger = logging.getLogger("file_service")


def _sync_read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _sync_write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _sync_append(path: str, content: str) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(content)


async def save_version(db: AsyncSession, file_id: uuid.UUID) -> None:
    """Snapshot current file content before any mutation."""
    f = await db.get(FileModel, file_id)
    if not f:
        return
    cnt = await db.execute(
        select(func.count()).select_from(FileVersion).where(FileVersion.file_id == file_id)
    )
    version_num = cnt.scalar_one() + 1
    try:
        content = await asyncio.to_thread(_sync_read, f.storage_path)
        db.add(FileVersion(id=uuid.uuid4(), file_id=file_id, version=version_num, content=content))
    except Exception as e:
        logger.warning("[file_service] save_version failed file_id=%s err=%s", file_id, e)


async def write_content(db: AsyncSession, user_id: int, file_id: uuid.UUID, content: str) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    try:
        await save_version(db, file_id)
        await asyncio.to_thread(_sync_write, f.storage_path, content)
        await db.execute(delete(FileChunk).where(FileChunk.file_id == file_id))
        f.upload_status = "uploaded"
        await db.commit()
        asyncio.create_task(process_file_async(file_id, f.storage_path, f.mime_type))
        record_tool_call("write_file")
        logger.info("[file_service] write_content file_id=%s chars=%d", file_id, len(content))
        return f"File updated ({len(content):,} chars). Re-embedding in background."
    except Exception as e:
        logger.warning("[file_service] write_content failed file_id=%s err=%s", file_id, e)
        return f"Error writing file: {e}"


async def append_content(db: AsyncSession, user_id: int, file_id: uuid.UUID, content: str) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    try:
        await save_version(db, file_id)
        separator = "\n\n" if content and not content.startswith("\n") else ""
        await asyncio.to_thread(_sync_append, f.storage_path, separator + content)
        await db.execute(delete(FileChunk).where(FileChunk.file_id == file_id))
        f.upload_status = "uploaded"
        await db.commit()
        asyncio.create_task(process_file_async(file_id, f.storage_path, f.mime_type))
        record_tool_call("append_to_file")
        logger.info("[file_service] append_content file_id=%s chars=%d", file_id, len(content))
        return f"Appended {len(content):,} chars. Re-embedding in background."
    except Exception as e:
        logger.warning("[file_service] append_content failed file_id=%s err=%s", file_id, e)
        return f"Error appending: {e}"


def _fuzzy_replace(content: str, old_text: str, new_text: str) -> tuple[str, bool]:
    """Exact → normalized line endings → stripped edges."""
    if old_text in content:
        return content.replace(old_text, new_text, 1), True
    n_old = old_text.replace("\r\n", "\n")
    n_con = content.replace("\r\n", "\n")
    if n_old in n_con:
        idx = n_con.index(n_old)
        return content[:idx] + new_text + content[idx + len(n_old):], True
    stripped = old_text.strip()
    if stripped and stripped in content:
        idx = content.index(stripped)
        return content[:idx] + new_text + content[idx + len(stripped):], True
    return content, False


async def patch_content(
    db:       AsyncSession,
    user_id:  int,
    file_id:  uuid.UUID,
    old_text: str,
    new_text: str,
) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    try:
        current = await asyncio.to_thread(_sync_read, f.storage_path)
        updated, found = _fuzzy_replace(current, old_text, new_text)
        if not found:
            return "Error: text not found in file. Use read_file to get the exact text, then retry."
        await save_version(db, file_id)
        await asyncio.to_thread(_sync_write, f.storage_path, updated)
        await db.execute(delete(FileChunk).where(FileChunk.file_id == file_id))
        f.upload_status = "uploaded"
        await db.commit()
        asyncio.create_task(process_file_async(file_id, f.storage_path, f.mime_type))
        record_tool_call("patch_file")
        logger.info("[file_service] patch_content file_id=%s", file_id)
        return f"Patched: replaced {len(old_text):,} chars with {len(new_text):,} chars. Re-embedding in background."
    except Exception as e:
        logger.warning("[file_service] patch_content failed file_id=%s err=%s", file_id, e)
        return f"Error patching: {e}"


async def restore_version(
    db:         AsyncSession,
    user_id:    int,
    file_id:    uuid.UUID,
    version_id: uuid.UUID,
) -> str | None:
    """Restore a version. Returns content on success, None on not found."""
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return None
    v = await db.get(FileVersion, version_id)
    if not v or v.file_id != file_id:
        return None
    await write_content(db, user_id, file_id, v.content)
    return v.content
