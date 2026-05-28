import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ConversationFile, File as FileModel
from services.file_service import append_content, patch_content, write_content
from storage.storage_manager import StorageManager

logger = logging.getLogger("tools")

MAX_FILE_READ = 100_000


async def _list_files(db: AsyncSession, conv_id: uuid.UUID) -> str:
    result = await db.execute(
        select(FileModel.id, FileModel.filename, FileModel.size_bytes, FileModel.upload_status)
        .join(ConversationFile, ConversationFile.file_id == FileModel.id)
        .where(ConversationFile.conversation_id == conv_id)
    )
    rows = result.all()
    if not rows:
        return "No files attached to this conversation."
    lines = [
        f"- {r.filename} (id={r.id}, size={r.size_bytes} bytes, status={r.upload_status})"
        for r in rows
    ]
    logger.info("[tools] list_files conv=%s count=%d", conv_id, len(rows))
    return "\n".join(lines)


def _sync_read_file_content(path: str, max_size: int) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read(max_size)


async def _read_file(db: AsyncSession, user_id: int, file_id: uuid.UUID) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    try:
        content = await asyncio.to_thread(_sync_read_file_content, f.storage_path, MAX_FILE_READ)
        truncated = len(content) == MAX_FILE_READ
        logger.info("[tools] read_file file_id=%s chars=%d truncated=%s", file_id, len(content), truncated)
        if truncated:
            content += f"\n\n[File truncated at {MAX_FILE_READ:,} characters]"
        return content
    except Exception as e:
        logger.warning("[tools] read_file failed file_id=%s err=%s", file_id, e)
        return f"Error reading file: {e}"


async def _write_file(db: AsyncSession, user_id: int, file_id: uuid.UUID, content: str) -> str:
    return await write_content(db, user_id, file_id, content)


async def _create_file(
    db:      AsyncSession,
    user_id: int,
    conv_id: uuid.UUID,
    name:    str,
    content: str,
) -> str:
    from services.processor import process_file_async
    storage = StorageManager()
    try:
        storage_path, size_bytes = await storage.save_text(content, name[:80])
        f = FileModel(
            user_id       = user_id,
            filename      = name[:255],
            mime_type     = "text/plain",
            size_bytes    = size_bytes,
            storage_path  = storage_path,
            upload_status = "uploaded",
        )
        db.add(f)
        await db.flush()
        db.add(ConversationFile(conversation_id=conv_id, file_id=f.id))
        await db.commit()
        asyncio.create_task(process_file_async(f.id, storage_path, "text/plain"))
        logger.info("[tools] create_file file_id=%s name=%s", f.id, name)
        return f"File '{name}' created and attached to conversation (id={f.id}). Processing in background."
    except Exception as e:
        logger.warning("[tools] create_file failed name=%s err=%s", name, e)
        return f"Error creating file: {e}"


async def _append_to_file(db: AsyncSession, user_id: int, file_id: uuid.UUID, content: str) -> str:
    return await append_content(db, user_id, file_id, content)


async def _patch_file(
    db:       AsyncSession,
    user_id:  int,
    file_id:  uuid.UUID,
    old_text: str,
    new_text: str,
) -> str:
    return await patch_content(db, user_id, file_id, old_text, new_text)
