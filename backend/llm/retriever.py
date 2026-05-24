import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import AsyncSessionLocal
from models import MessageEmbedding

logger = logging.getLogger("retriever")


async def retrieve(
    db: AsyncSession,
    query_embedding: list[float],
    conversation_id: uuid.UUID,
    top_k: int = 3,
) -> list[str]:
    try:
        result = await db.execute(
            select(MessageEmbedding.content_snippet)
            .where(MessageEmbedding.conversation_id == conversation_id)
            .order_by(MessageEmbedding.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        return list(result.scalars().all())
    except Exception as e:
        logger.warning("[retriever] retrieve failed conv=%s err=%s", conversation_id, e)
        return []


async def store_exchange(
    message_id:      uuid.UUID,
    conversation_id: uuid.UUID,
    user_text:       str,
    assistant_text:  str,
    embedding:       list[float],
) -> None:
    snippet = f"User: {user_text[:300]}\nAssistant: {assistant_text[:400]}"
    async with AsyncSessionLocal() as db:
        try:
            db.add(MessageEmbedding(
                message_id      = message_id,
                conversation_id = conversation_id,
                content_snippet = snippet,
                embedding       = embedding,
            ))
            await db.commit()
            logger.debug("[retriever] stored embedding msg=%s", message_id)
        except Exception:
            logger.exception("[retriever] store_exchange failed msg=%s", message_id)
