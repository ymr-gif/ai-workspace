import logging
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import AsyncSessionLocal
from models import FileChunk, MessageEmbedding

logger = logging.getLogger("retriever")


async def _bm25_file_chunks(
    db:       AsyncSession,
    file_ids: list[uuid.UUID],
    query:    str,
    limit:    int,
) -> list[tuple]:
    result = await db.execute(
        select(
            FileChunk.id, FileChunk.file_id, FileChunk.content,
            func.coalesce(
                func.ts_rank(text("content_tsv"), func.websearch_to_tsquery('simple', text(":q"))),
                0.0
            ).label("rank")
        )
        .where(FileChunk.file_id.in_(file_ids))
        .where(text("content_tsv @@ websearch_to_tsquery('simple', :q)"))
        .order_by(text("ts_rank(content_tsv, websearch_to_tsquery('simple', :q)) DESC"))
        .limit(limit)
        .params(q=query)
    )
    return [(r.id, r.file_id, r.content, float(r.rank)) for r in result.all()]


async def _bm25_message_embeddings(
    db:    AsyncSession,
    where: list,
    query: str,
    limit: int,
) -> list[tuple]:
    result = await db.execute(
        select(
            MessageEmbedding.id, MessageEmbedding.conversation_id, MessageEmbedding.content_snippet,
            func.coalesce(
                func.ts_rank(text("content_tsv"), func.websearch_to_tsquery('simple', text(":q"))),
                0.0
            ).label("rank")
        )
        .where(*where)
        .where(text("content_tsv @@ websearch_to_tsquery('simple', :q)"))
        .order_by(text("ts_rank(content_tsv, websearch_to_tsquery('simple', :q)) DESC"))
        .limit(limit)
        .params(q=query)
    )
    return [(r.id, r.conversation_id, r.content_snippet, float(r.rank)) for r in result.all()]


async def get_relevance_scores(
    db:              AsyncSession,
    conversation_id: uuid.UUID,
    query_embedding: list[float],
    message_ids:     list | None = None,
) -> dict[uuid.UUID, float]:
    try:
        q = (
            select(
                MessageEmbedding.message_id,
                (1.0 - MessageEmbedding.embedding.cosine_distance(query_embedding)).label("sim"),
            )
            .where(MessageEmbedding.conversation_id == conversation_id)
        )
        if message_ids:
            q = q.where(MessageEmbedding.message_id.in_(message_ids))
        result = await db.execute(q)
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
        except IntegrityError:
            # Benign race: the message/conversation was deleted before this async
            # embed committed (FK violation). Roll back quietly — not an error.
            await db.rollback()
            logger.debug("[retriever] store_exchange skipped — message %s no longer exists", message_id)
        except Exception:
            await db.rollback()
            logger.exception("[retriever] store_exchange failed msg=%s", message_id)
