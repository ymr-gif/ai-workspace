import logging
import uuid
from datetime import timedelta

from arq.connections import RedisSettings
from arq.worker import Retry
from sqlalchemy import func, select

from config import REDIS_URL
from core.db import AsyncSessionLocal
from models import Conversation, File, FileChunk, Message, MessageEmbedding, UserInsight, UserMemory
from services.processor import _process

logger = logging.getLogger("arq_worker")

_RETRY_DELAYS = [5, 30, 120]


async def process_file_job(ctx, file_id: str, storage_path: str, mime_type: str) -> None:
    attempt = ctx.get("job_try", 1)
    async with AsyncSessionLocal() as db:
        try:
            await _process(db, uuid.UUID(file_id), storage_path, mime_type)
        except Exception:
            logger.exception("[arq] failed file_id=%s attempt=%d", file_id, attempt)
            if attempt <= len(_RETRY_DELAYS):
                raise Retry(defer=timedelta(seconds=_RETRY_DELAYS[attempt - 1]))
            row = await db.get(File, uuid.UUID(file_id))
            if row:
                row.upload_status = "error"
                await db.commit()


async def generate_insight_job(ctx, user_id: int) -> None:
    from llm.agency import generate_user_insight

    async with AsyncSessionLocal() as db:
        # Skip if 3+ unread insights already waiting
        unread = await db.scalar(
            select(func.count()).where(
                UserInsight.user_id == user_id,
                UserInsight.is_read == False,
            )
        )
        if (unread or 0) >= 3:
            return

        memory_row = await db.get(UserMemory, user_id)
        memory = (memory_row.content or "") if memory_row else ""

        msgs_result = await db.execute(
            select(Message.content)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id, Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        recent_topics = "\n".join(f"- {m[:100]}" for m in msgs_result.scalars().all())

        insight = await generate_user_insight(user_id, memory, recent_topics)
        if not insight:
            return

        db.add(UserInsight(user_id=user_id, content=insight))
        await db.commit()
        logger.info("[arq] insight generated user=%s", user_id)


async def re_embed_batch_job(ctx, table: str, offset: int, batch_size: int) -> None:
    from llm.embeddings import embed
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        if table == "file_chunk":
            result = await db.execute(
                select(FileChunk).order_by(FileChunk.created_at).offset(offset).limit(batch_size)
            )
            rows = result.scalars().all()
            for chunk in rows:
                emb = await embed(chunk.content[:2000], input_type="passage")
                if emb:
                    chunk.embedding = emb
            await db.commit()
            logger.info("[re_embed] file_chunks offset=%d count=%d", offset, len(rows))

        elif table == "message_embedding":
            result = await db.execute(
                select(MessageEmbedding).order_by(MessageEmbedding.created_at).offset(offset).limit(batch_size)
            )
            rows = result.scalars().all()
            for me in rows:
                emb = await embed(me.content_snippet[:2000], input_type="passage")
                if emb:
                    me.embedding = emb
            await db.commit()
            logger.info("[re_embed] message_embeddings offset=%d count=%d", offset, len(rows))


async def compact_memory_job(ctx, user_id: int) -> None:
    from llm.summarizer import compact_memory

    try:
        await compact_memory(user_id)
        logger.info("[arq] compact_memory done user_id=%s", user_id)
    except Exception:
        logger.exception("[arq] compact_memory failed user_id=%s", user_id)


class WorkerSettings:
    functions = [process_file_job, generate_insight_job, re_embed_batch_job, compact_memory_job]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 10
    max_tries = 4
