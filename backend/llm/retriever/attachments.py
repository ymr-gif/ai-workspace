import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ConversationFile, File as FileModel

logger = logging.getLogger("retriever")


async def get_conversation_file_ids(
    db:      AsyncSession,
    conv_id: uuid.UUID,
) -> list[uuid.UUID]:
    try:
        result = await db.execute(
            select(ConversationFile.file_id)
            .where(ConversationFile.conversation_id == conv_id)
        )
        ids = list(result.scalars().all())
        if ids:
            logger.info("[retriever] conv=%s attached_files=%d", conv_id, len(ids))
        return ids
    except Exception as e:
        logger.warning("[retriever] get_conversation_file_ids failed err=%s", e)
        return []


async def get_conversation_files(
    db:      AsyncSession,
    conv_id: uuid.UUID,
) -> tuple[list[uuid.UUID], list[str]]:
    try:
        result = await db.execute(
            select(FileModel.id, FileModel.filename)
            .join(ConversationFile, ConversationFile.file_id == FileModel.id)
            .where(ConversationFile.conversation_id == conv_id)
        )
        rows  = result.all()
        ids   = [r.id       for r in rows]
        names = [r.filename for r in rows]
        if ids:
            logger.info("[retriever] conv=%s attached_files=%d names=%s", conv_id, len(ids), names)
        return ids, names
    except Exception as e:
        logger.warning("[retriever] get_conversation_files failed err=%s", e)
        return [], []
