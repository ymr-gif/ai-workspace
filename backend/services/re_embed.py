import logging

from sqlalchemy import func, select

from config import MODEL_EMBEDDING
from core.db import AsyncSessionLocal
from models import FileChunk, MessageEmbedding, SystemConfig

logger = logging.getLogger("re_embed")

BATCH_SIZE = 100
_EMBED_MODEL_KEY = "embedding_model"


async def check_and_queue_re_embed() -> None:
    async with AsyncSessionLocal() as db:
        row    = await db.get(SystemConfig, _EMBED_MODEL_KEY)
        stored = row.value if row else None
        if stored == MODEL_EMBEDDING:
            return

        logger.info("[re_embed] model changed %s -> %s; queueing re-embed", stored, MODEL_EMBEDDING)
        if row:
            row.value = MODEL_EMBEDDING
        else:
            db.add(SystemConfig(key=_EMBED_MODEL_KEY, value=MODEL_EMBEDDING))
        await db.commit()

    await _queue_all_batches()


async def queue_re_embed_force() -> int:
    async with AsyncSessionLocal() as db:
        row = await db.get(SystemConfig, _EMBED_MODEL_KEY)
        if row:
            row.value = MODEL_EMBEDDING
        else:
            db.add(SystemConfig(key=_EMBED_MODEL_KEY, value=MODEL_EMBEDDING))
        await db.commit()

    return await _queue_all_batches()


async def _queue_all_batches() -> int:
    from core.arq_pool import get_arq_pool

    async with AsyncSessionLocal() as db:
        chunk_count = (await db.scalar(select(func.count()).select_from(FileChunk))) or 0
        msg_count   = (await db.scalar(select(func.count()).select_from(MessageEmbedding))) or 0

    pool = get_arq_pool()
    if not pool:
        logger.warning("[re_embed] arq pool unavailable, skipping queue")
        return 0

    for offset in range(0, chunk_count, BATCH_SIZE):
        await pool.enqueue_job("re_embed_batch_job", "file_chunk", offset, BATCH_SIZE)

    for offset in range(0, msg_count, BATCH_SIZE):
        await pool.enqueue_job("re_embed_batch_job", "message_embedding", offset, BATCH_SIZE)

    total = chunk_count + msg_count
    logger.info("[re_embed] queued %d items (%d chunks, %d msg embeddings)", total, chunk_count, msg_count)
    return total
