import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import AsyncSessionLocal
from models import Conversation, ConversationFile, File as FileModel, FileChunk, MessageEmbedding

logger = logging.getLogger("retriever")

_REFERENCE_KEYWORDS = {
    "earlier", "before", "you said", "remember", "last time",
    "previously", "we discussed", "you mentioned", "you told",
    "recall", "forgot", "forget", "back to", "as we talked",
    "you explained", "you showed", "we covered",
}

_RRF_K    = 60   # RRF constant — higher = less rank-sensitive
_FETCH_N  = 20   # candidates per side before merge


def is_reference_query(text_: str) -> bool:
    lower = text_.lower()
    return any(kw in lower for kw in _REFERENCE_KEYWORDS)


def _rrf_merge(
    vector_rows: list[tuple],
    bm25_rows:   list[tuple],
    top_k:       int,
) -> list[str]:
    """Reciprocal Rank Fusion: combine (id, content) lists from both sources."""
    scores:   dict = {}
    contents: dict = {}
    for rank, (rid, content) in enumerate(vector_rows):
        scores[rid]   = scores.get(rid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        contents[rid] = content
    for rank, (rid, content) in enumerate(bm25_rows):
        scores[rid]   = scores.get(rid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        contents[rid] = content
    sorted_ids = sorted(scores, key=lambda x: -scores[x])
    return [contents[i] for i in sorted_ids[:top_k]]


async def _bm25_file_chunks(
    db:       AsyncSession,
    file_ids: list[uuid.UUID],
    query:    str,
    limit:    int,
) -> list[tuple]:
    result = await db.execute(
        select(FileChunk.id, FileChunk.content)
        .where(FileChunk.file_id.in_(file_ids))
        .where(text("content_tsv @@ websearch_to_tsquery('simple', :q)"))
        .order_by(text("ts_rank(content_tsv, websearch_to_tsquery('simple', :q)) DESC"))
        .limit(limit)
        .params(q=query)
    )
    return [(r.id, r.content) for r in result.all()]


async def _bm25_message_embeddings(
    db:    AsyncSession,
    where: list,
    query: str,
    limit: int,
) -> list[tuple]:
    result = await db.execute(
        select(MessageEmbedding.id, MessageEmbedding.content_snippet)
        .where(*where)
        .where(text("content_tsv @@ websearch_to_tsquery('simple', :q)"))
        .order_by(text("ts_rank(content_tsv, websearch_to_tsquery('simple', :q)) DESC"))
        .limit(limit)
        .params(q=query)
    )
    return [(r.id, r.content_snippet) for r in result.all()]


async def retrieve(
    db:              AsyncSession,
    query_embedding: list[float],
    conversation_id: uuid.UUID,
    top_k:           int = 3,
    query_text:      str = "",
) -> list[str]:
    try:
        vec_result = await db.execute(
            select(MessageEmbedding.id, MessageEmbedding.content_snippet)
            .where(MessageEmbedding.conversation_id == conversation_id)
            .order_by(MessageEmbedding.embedding.cosine_distance(query_embedding))
            .limit(_FETCH_N)
        )
        vector_rows = [(r.id, r.content_snippet) for r in vec_result.all()]

        bm25_rows: list[tuple] = []
        if query_text.strip():
            try:
                bm25_rows = await _bm25_message_embeddings(
                    db,
                    [MessageEmbedding.conversation_id == conversation_id],
                    query_text,
                    _FETCH_N,
                )
            except Exception as e:
                logger.warning("[retriever] bm25 retrieve failed conv=%s err=%s", conversation_id, e)

        if bm25_rows:
            return _rrf_merge(vector_rows, bm25_rows, top_k)
        return [c for _, c in vector_rows[:top_k]]

    except Exception as e:
        logger.warning("[retriever] retrieve failed conv=%s err=%s", conversation_id, e)
        return []


async def retrieve_global(
    db:              AsyncSession,
    query_embedding: list[float],
    exclude_conv_id: uuid.UUID,
    user_id:         int,
    top_k:           int = 5,
    query_text:      str = "",
) -> list[str]:
    try:
        vec_result = await db.execute(
            select(MessageEmbedding.id, MessageEmbedding.content_snippet)
            .join(Conversation, MessageEmbedding.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                MessageEmbedding.conversation_id != exclude_conv_id,
            )
            .order_by(MessageEmbedding.embedding.cosine_distance(query_embedding))
            .limit(_FETCH_N)
        )
        vector_rows = [(r.id, r.content_snippet) for r in vec_result.all()]

        bm25_rows: list[tuple] = []
        if query_text.strip():
            try:
                bm25_rows = await _bm25_message_embeddings(
                    db,
                    [
                        MessageEmbedding.conversation_id.in_(
                            select(Conversation.id)
                            .where(Conversation.user_id == user_id)
                            .where(Conversation.id != exclude_conv_id)
                        )
                    ],
                    query_text,
                    _FETCH_N,
                )
            except Exception as e:
                logger.warning("[retriever] bm25 retrieve_global failed user=%s err=%s", user_id, e)

        if bm25_rows:
            return _rrf_merge(vector_rows, bm25_rows, top_k)
        return [c for _, c in vector_rows[:top_k]]

    except Exception as e:
        logger.warning("[retriever] retrieve_global failed user=%s err=%s", user_id, e)
        return []


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
        except Exception:
            logger.exception("[retriever] store_exchange failed msg=%s", message_id)


async def retrieve_from_files(
    db:              AsyncSession,
    query_embedding: list[float],
    file_ids:        list[uuid.UUID],
    top_k:           int = 5,
    query_text:      str = "",
) -> list[str]:
    if not file_ids:
        return []
    try:
        vec_result = await db.execute(
            select(FileChunk.id, FileChunk.content)
            .where(FileChunk.file_id.in_(file_ids))
            .where(FileChunk.embedding.isnot(None))
            .order_by(FileChunk.embedding.cosine_distance(query_embedding))
            .limit(_FETCH_N)
        )
        vector_rows = [(r.id, r.content) for r in vec_result.all()]

        bm25_rows: list[tuple] = []
        if query_text.strip():
            try:
                bm25_rows = await _bm25_file_chunks(db, file_ids, query_text, _FETCH_N)
            except Exception as e:
                logger.warning("[retriever] bm25 file search failed err=%s", e)

        if bm25_rows:
            chunks = _rrf_merge(vector_rows, bm25_rows, top_k)
        else:
            chunks = [c for _, c in vector_rows[:top_k]]

        logger.info("[retriever] retrieve_from_files files=%d vector=%d bm25=%d merged=%d",
                    len(file_ids), len(vector_rows), len(bm25_rows), len(chunks))
        return chunks
    except Exception as e:
        logger.warning("[retriever] retrieve_from_files failed err=%s", e)
        return []


async def retrieve_files_sequential(
    db:       AsyncSession,
    file_ids: list[uuid.UUID],
    top_k:    int = 10,
) -> list[str]:
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
        chunks = list(result.scalars().all())
        logger.info("[retriever] retrieve_files_sequential files=%d chunks=%d", len(file_ids), len(chunks))
        return chunks
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
