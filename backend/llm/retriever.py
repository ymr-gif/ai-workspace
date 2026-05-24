import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import AsyncSessionLocal
from models import Conversation, ConversationFile, FileChunk, MessageEmbedding

logger = logging.getLogger("retriever")

_REFERENCE_KEYWORDS = {
    "earlier", "before", "you said", "remember", "last time",
    "previously", "we discussed", "you mentioned", "you told",
    "recall", "forgot", "forget", "back to", "as we talked",
    "you explained", "you showed", "we covered",
}


def is_reference_query(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _REFERENCE_KEYWORDS)


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


async def retrieve_global(
    db: AsyncSession,
    query_embedding: list[float],
    exclude_conv_id: uuid.UUID,
    user_id: int,
    top_k: int = 5,
) -> list[str]:
    """Cross-conversation search for on-demand rehydration."""
    try:
        result = await db.execute(
            select(MessageEmbedding.content_snippet)
            .join(Conversation, MessageEmbedding.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                MessageEmbedding.conversation_id != exclude_conv_id,
            )
            .order_by(MessageEmbedding.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        return list(result.scalars().all())
    except Exception as e:
        logger.warning("[retriever] retrieve_global failed user=%s err=%s", user_id, e)
        return []


async def get_relevance_scores(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    query_embedding: list[float],
) -> dict[uuid.UUID, float]:
    """Returns {assistant_message_id: cosine_similarity} for importance weighting."""
    try:
        result = await db.execute(
            select(
                MessageEmbedding.message_id,
                (1.0 - MessageEmbedding.embedding.cosine_distance(query_embedding)).label("sim"),
            )
            .where(MessageEmbedding.conversation_id == conversation_id)
        )
        return {row.message_id: float(row.sim) for row in result}
    except Exception as e:
        logger.warning("[retriever] get_relevance_scores failed conv=%s err=%s", conversation_id, e)
        return {}


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


async def retrieve_from_files(
    db:              AsyncSession,
    query_embedding: list[float],
    file_ids:        list[uuid.UUID],
    top_k:           int = 5,
) -> list[str]:
    """Retrieve top-k chunks from the given files via cosine similarity."""
    if not file_ids:
        return []
    try:
        result = await db.execute(
            select(FileChunk.content)
            .where(FileChunk.file_id.in_(file_ids))
            .where(FileChunk.embedding.isnot(None))
            .order_by(FileChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        return list(result.scalars().all())
    except Exception as e:
        logger.warning("[retriever] retrieve_from_files failed err=%s", e)
        return []


async def retrieve_files_sequential(
    db:       AsyncSession,
    file_ids: list[uuid.UUID],
    top_k:    int = 10,
) -> list[str]:
    """Fallback: return first top_k chunks by index when no query embedding available."""
    if not file_ids:
        return []
    try:
        result = await db.execute(
            select(FileChunk.content)
            .where(FileChunk.file_id.in_(file_ids))
            .where(FileChunk.embedding.isnot(None))
            .order_by(FileChunk.chunk_index.asc())
            .limit(top_k)
        )
        return list(result.scalars().all())
    except Exception as e:
        logger.warning("[retriever] retrieve_files_sequential failed err=%s", e)
        return []


async def get_conversation_file_ids(
    db:      AsyncSession,
    conv_id: uuid.UUID,
) -> list[uuid.UUID]:
    try:
        result = await db.execute(
            select(ConversationFile.file_id)
            .where(ConversationFile.conversation_id == conv_id)
        )
        return list(result.scalars().all())
    except Exception as e:
        logger.warning("[retriever] get_conversation_file_ids failed err=%s", e)
        return []
