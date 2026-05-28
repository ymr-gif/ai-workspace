import logging
import uuid

from sqlalchemy import func, select, text
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


def _weighted_merge(
    vector_rows: list[tuple],  # (id, source_id, content, raw_sim)
    bm25_rows:   list[tuple],  # (id, source_id, content, raw_rank)
    top_k:       int,
    alpha:       float = 0.5,
) -> list[dict]:
    """Weighted fusion: normalize raw scores to [0,1], then alpha*dense + (1-alpha)*sparse."""
    dense_scores:  dict = {}
    sparse_scores: dict = {}
    contents:      dict = {}
    source_ids:    dict = {}

    for rid, src_id, content, raw in vector_rows:
        dense_scores[rid]  = raw
        contents[rid]      = content
        source_ids[rid]    = src_id

    for rid, src_id, content, raw in bm25_rows:
        sparse_scores[rid] = raw
        contents.setdefault(rid, content)
        source_ids.setdefault(rid, src_id)

    max_dense  = max(dense_scores.values())  if dense_scores  else 1.0
    max_sparse = max(sparse_scores.values()) if sparse_scores else 1.0

    all_ids    = set(dense_scores) | set(sparse_scores)
    result = []
    for i in all_ids:
        d     = dense_scores.get(i, 0.0)  / max_dense  if max_dense  > 0 else 0.0
        s     = sparse_scores.get(i, 0.0) / max_sparse if max_sparse > 0 else 0.0
        final = alpha * d + (1.0 - alpha) * s
        result.append({
            "chunk_id":      i,
            "source_id":     source_ids.get(i),
            "content":       contents[i],
            "dense_score":   round(d, 6),
            "sparse_score":  round(s, 6),
            "final_score":   round(final, 6),
            "retrieval_type": "weighted",
        })

    result.sort(key=lambda x: -x["final_score"])
    return result[:top_k]


def _rrf_merge(
    vector_rows: list[tuple],
    bm25_rows:   list[tuple],
    top_k:       int,
) -> list[dict]:
    """Reciprocal Rank Fusion: combine (id, source_id, content) triples from both sources."""
    dense:      dict = {}
    sparse:     dict = {}
    contents:   dict = {}
    source_ids: dict = {}
    for rank, (rid, src_id, content) in enumerate(vector_rows):
        dense[rid]      = 1.0 / (_RRF_K + rank + 1)
        contents[rid]   = content
        source_ids[rid] = src_id
    for rank, (rid, src_id, content) in enumerate(bm25_rows):
        sparse[rid] = 1.0 / (_RRF_K + rank + 1)
        contents[rid] = content
        source_ids.setdefault(rid, src_id)
    all_ids    = set(dense) | set(sparse)
    sorted_ids = sorted(all_ids, key=lambda x: -(dense.get(x, 0.0) + sparse.get(x, 0.0)))
    result = []
    for i in sorted_ids[:top_k]:
        d   = round(dense.get(i, 0.0), 6)
        s   = round(sparse.get(i, 0.0), 6)
        rtype = "+".join(sorted(filter(None, ["bm25" if s else "", "vector" if d else ""])))
        result.append({
            "chunk_id":      i,
            "source_id":     source_ids.get(i),
            "content":       contents[i],
            "dense_score":   d,
            "sparse_score":  s,
            "final_score":   round(d + s, 6),
            "retrieval_type": rtype,
        })
    return result


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


async def retrieve(
    db:              AsyncSession,
    query_embedding: list[float],
    conversation_id: uuid.UUID,
    top_k:           int = 3,
    query_text:      str = "",
    *,
    fusion_mode:     str   = "rrf",
    k_dense:         int   = 20,
    k_sparse:        int   = 20,
    alpha:           float = 0.5,
) -> list[str]:
    try:
        vec_result = await db.execute(
            select(
                MessageEmbedding.id, MessageEmbedding.conversation_id, MessageEmbedding.content_snippet,
                (1.0 - MessageEmbedding.embedding.cosine_distance(query_embedding)).label("sim")
            )
            .where(MessageEmbedding.conversation_id == conversation_id)
            .order_by(MessageEmbedding.embedding.cosine_distance(query_embedding))
            .limit(k_dense)
        )
        vector_rows = [(r.id, r.conversation_id, r.content_snippet, float(r.sim)) for r in vec_result.all()]

        bm25_rows: list[tuple] = []
        if query_text.strip():
            try:
                bm25_rows = await _bm25_message_embeddings(
                    db,
                    [MessageEmbedding.conversation_id == conversation_id],
                    query_text,
                    k_sparse,
                )
            except Exception as e:
                logger.warning("[retriever] bm25 retrieve failed conv=%s err=%s", conversation_id, e)

        if fusion_mode == "weighted":
            return _weighted_merge(vector_rows, bm25_rows, top_k, alpha)
        if bm25_rows:
            return _rrf_merge(
                [(r[0], r[1], r[2]) for r in vector_rows],
                [(r[0], r[1], r[2]) for r in bm25_rows],
                top_k
            )
        return [
            {
                "chunk_id":      rid,
                "source_id":     src_id,
                "content":       c,
                "dense_score":   round(1.0 / (_RRF_K + rank + 1), 6),
                "sparse_score":  0.0,
                "final_score":   round(1.0 / (_RRF_K + rank + 1), 6),
                "retrieval_type": "vector",
            }
            for rank, (rid, src_id, c, _) in enumerate(vector_rows[:top_k])
        ]

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
    *,
    fusion_mode:     str   = "rrf",
    k_dense:         int   = 20,
    k_sparse:        int   = 20,
    alpha:           float = 0.5,
) -> list[str]:
    try:
        vec_result = await db.execute(
            select(
                MessageEmbedding.id, MessageEmbedding.conversation_id, MessageEmbedding.content_snippet,
                (1.0 - MessageEmbedding.embedding.cosine_distance(query_embedding)).label("sim")
            )
            .join(Conversation, MessageEmbedding.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                MessageEmbedding.conversation_id != exclude_conv_id,
            )
            .order_by(MessageEmbedding.embedding.cosine_distance(query_embedding))
            .limit(k_dense)
        )
        vector_rows = [(r.id, r.conversation_id, r.content_snippet, float(r.sim)) for r in vec_result.all()]

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
                    k_sparse,
                )
            except Exception as e:
                logger.warning("[retriever] bm25 retrieve_global failed user=%s err=%s", user_id, e)

        if fusion_mode == "weighted":
            return _weighted_merge(vector_rows, bm25_rows, top_k, alpha)
        if bm25_rows:
            return _rrf_merge(
                [(r[0], r[1], r[2]) for r in vector_rows],
                [(r[0], r[1], r[2]) for r in bm25_rows],
                top_k
            )
        return [
            {
                "chunk_id":      rid,
                "source_id":     src_id,
                "content":       c,
                "dense_score":   round(1.0 / (_RRF_K + rank + 1), 6),
                "sparse_score":  0.0,
                "final_score":   round(1.0 / (_RRF_K + rank + 1), 6),
                "retrieval_type": "vector",
            }
            for rank, (rid, src_id, c, _) in enumerate(vector_rows[:top_k])
        ]

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
    *,
    fusion_mode:     str   = "rrf",
    k_dense:         int   = 20,
    k_sparse:        int   = 20,
    alpha:           float = 0.5,
) -> list[str]:
    if not file_ids:
        return []
    try:
        vec_result = await db.execute(
            select(
                FileChunk.id, FileChunk.file_id, FileChunk.content,
                (1.0 - FileChunk.embedding.cosine_distance(query_embedding)).label("sim")
            )
            .where(FileChunk.file_id.in_(file_ids))
            .where(FileChunk.embedding.isnot(None))
            .order_by(FileChunk.embedding.cosine_distance(query_embedding))
            .limit(k_dense)
        )
        vector_rows = [(r.id, r.file_id, r.content, float(r.sim)) for r in vec_result.all()]

        bm25_rows: list[tuple] = []
        if query_text.strip():
            try:
                bm25_rows = await _bm25_file_chunks(db, file_ids, query_text, k_sparse)
            except Exception as e:
                logger.warning("[retriever] bm25 file search failed err=%s", e)

        if fusion_mode == "weighted":
            chunks = _weighted_merge(vector_rows, bm25_rows, top_k, alpha)
        elif bm25_rows:
            chunks = _rrf_merge(
                [(r[0], r[1], r[2]) for r in vector_rows],
                [(r[0], r[1], r[2]) for r in bm25_rows],
                top_k
            )
        else:
            chunks = [
                {
                    "chunk_id":      rid,
                    "source_id":     src_id,
                    "content":       c,
                    "dense_score":   round(1.0 / (_RRF_K + rank + 1), 6),
                    "sparse_score":  0.0,
                    "final_score":   round(1.0 / (_RRF_K + rank + 1), 6),
                    "retrieval_type": "vector",
                }
                for rank, (rid, src_id, c, _) in enumerate(vector_rows[:top_k])
            ]

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
            select(FileChunk.id, FileChunk.file_id, FileChunk.content)
            .where(FileChunk.file_id.in_(file_ids))
            .where(FileChunk.embedding.isnot(None))
            .order_by(FileChunk.chunk_index.asc())
            .limit(top_k)
        )
        rows   = result.all()
        chunks = [
            {
                "chunk_id":      r.id,
                "source_id":     r.file_id,
                "content":       r.content,
                "dense_score":   0.0,
                "sparse_score":  0.0,
                "final_score":   0.0,
                "retrieval_type": "sequential",
            }
            for r in rows
        ]
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
