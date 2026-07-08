import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import Conversation, ConversationFile, File as FileModel, FileChunk, MessageEmbedding
from .fusion import _RRF_K, _weighted_merge, _rrf_merge
from .queries import _bm25_file_chunks, _bm25_message_embeddings

logger = logging.getLogger("retriever")

# Cross-conversation pool weighting (retrieve_global only). The global pool mixes
# every active conversation, so a bare cosine ranking lets stale, weakly-related
# exchanges bleed into context. Drop hits below the floor, and decay older ones so
# recent context wins ties.
_GLOBAL_SIM_FLOOR = 0.30          # cosine sim below this is treated as noise
_RECENCY_HALF_LIFE_DAYS = 14.0    # weight halves every two weeks


def _recency_weight(created_at: datetime | None, now: datetime) -> float:
    if created_at is None:
        return 1.0
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return 0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS)

_REFERENCE_KEYWORDS = {
    "earlier", "before", "you said", "remember", "last time",
    "previously", "we discussed", "you mentioned", "you told",
    "recall", "forgot", "forget", "back to", "as we talked",
    "you explained", "you showed", "we covered",
}


def is_reference_query(text_: str) -> bool:
    lower = text_.lower()
    return any(kw in lower for kw in _REFERENCE_KEYWORDS)


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
    debug:           bool  = False,
    exclude_message_ids: list | None = None,
) -> list[dict] | tuple[list[dict], list[dict]]:
    # C3 echo dedup: drop message-embeddings for messages already in the raw
    # history window sent verbatim this turn (structural — the previous exchange
    # would otherwise re-surface at ~1.00 sim and get re-answered). Empty/None →
    # no-op. Cross-conversation retrieval (retrieve_global) is untouched.
    _where = [MessageEmbedding.conversation_id == conversation_id]
    if exclude_message_ids:
        _where.append(MessageEmbedding.message_id.notin_(exclude_message_ids))

    _fusion = fusion_mode
    try:
        vec_result = await db.execute(
            select(
                MessageEmbedding.id, MessageEmbedding.conversation_id, MessageEmbedding.content_snippet,
                (1.0 - MessageEmbedding.embedding.cosine_distance(query_embedding)).label("sim")
            )
            .where(*_where)
            .order_by(MessageEmbedding.embedding.cosine_distance(query_embedding))
            .limit(k_dense)
        )
        vector_rows = [(r.id, r.conversation_id, r.content_snippet, float(r.sim)) for r in vec_result.all()]

        bm25_rows: list[tuple] = []
        if query_text.strip():
            try:
                bm25_rows = await _bm25_message_embeddings(
                    db,
                    list(_where),
                    query_text,
                    k_sparse,
                )
            except Exception as e:
                logger.warning("[retriever] bm25 retrieve failed conv=%s err=%s", conversation_id, e)

        if fusion_mode == "weighted":
            result = _weighted_merge(vector_rows, bm25_rows, top_k, alpha)
        elif bm25_rows:
            result = _rrf_merge(
                [(r[0], r[1], r[2]) for r in vector_rows],
                [(r[0], r[1], r[2]) for r in bm25_rows],
                top_k
            )
        else:
            result = [
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
        if debug:
            debug_info = [
                {"chunk_id": c["chunk_id"], "source_id": c["source_id"],
                 "score": c["final_score"], "rank": i + 1, "fusion_mode": _fusion}
                for i, c in enumerate(result)
            ]
            return result, debug_info
        return result

    except Exception as e:
        logger.warning("[retriever] retrieve failed conv=%s err=%s", conversation_id, e)
        return ([], []) if debug else []


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
                (1.0 - MessageEmbedding.embedding.cosine_distance(query_embedding)).label("sim"),
                MessageEmbedding.created_at,
            )
            .join(Conversation, MessageEmbedding.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                MessageEmbedding.conversation_id != exclude_conv_id,
                Conversation.is_archived == False,
            )
            .order_by(MessageEmbedding.embedding.cosine_distance(query_embedding))
            .limit(k_dense)
        )
        # Apply the similarity floor + recency decay, then re-rank by the weighted
        # score so the strongest *recent* hits lead the fusion step.
        now = datetime.now(timezone.utc)
        vector_rows = []
        for r in vec_result.all():
            sim = float(r.sim)
            if sim < _GLOBAL_SIM_FLOOR:
                continue
            weighted = sim * _recency_weight(r.created_at, now)
            vector_rows.append((r.id, r.conversation_id, r.content_snippet, weighted))
        vector_rows.sort(key=lambda row: row[3], reverse=True)

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
                            .where(Conversation.is_archived == False)
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
    debug:           bool  = False,
) -> list[dict] | tuple[list[dict], list[dict]]:
    _fusion = fusion_mode
    if not file_ids:
        return ([], []) if debug else []
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
        if debug:
            debug_info = [
                {"chunk_id": c["chunk_id"], "source_id": c["source_id"],
                 "score": c["final_score"], "rank": i + 1, "fusion_mode": _fusion}
                for i, c in enumerate(chunks)
            ]
            return chunks, debug_info
        return chunks
    except Exception as e:
        logger.warning("[retriever] retrieve_from_files failed err=%s", e)
        return ([], []) if debug else []


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
