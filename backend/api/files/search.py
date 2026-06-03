import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from llm.embeddings import embed
from models import File as FileModel, FileChunk, User

router = APIRouter()
logger = logging.getLogger("files.search")

_RRF_K = 60


def _fuse(
    vec_rows:     list[tuple],
    bm25_rows:    list[tuple],
    top_k:        int,
    fusion_mode:  str   = "rrf",
    alpha:        float = 0.5,
    k_dense:      int   = 20,
    k_sparse:     int   = 20,
    debug:        bool  = False,
) -> list[dict] | tuple[list[dict], list[dict]]:
    """Merge vector + BM25 results using RRF or weighted fusion.

    Each row: (cid, content, file_id, filename[, raw_score]).
    When debug=True, returns (results, debug_info).
    """
    scores: dict = {}
    meta:   dict = {}

    if fusion_mode == "weighted":
        dense_raw:  dict = {}
        sparse_raw: dict = {}
        for row in vec_rows:
            cid, content, file_id, filename, raw = row
            dense_raw[cid] = raw
            meta[cid] = (content, file_id, filename)
        for row in bm25_rows:
            cid, content, file_id, filename, raw = row
            sparse_raw[cid] = raw
            meta.setdefault(cid, (content, file_id, filename))

        max_dense  = max(dense_raw.values())  if dense_raw  else 1.0
        max_sparse = max(sparse_raw.values()) if sparse_raw else 1.0
        all_ids = set(dense_raw) | set(sparse_raw)
        for i in all_ids:
            d     = dense_raw.get(i, 0.0)  / max_dense  if max_dense  > 0 else 0.0
            s     = sparse_raw.get(i, 0.0) / max_sparse if max_sparse > 0 else 0.0
            scores[i] = alpha * d + (1.0 - alpha) * s
    else:
        for rank, row in enumerate(vec_rows):
            cid = row[0]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            meta[cid]   = (row[1], row[2], row[3])
        for rank, row in enumerate(bm25_rows):
            cid = row[0]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            meta[cid]   = (row[1], row[2], row[3])

    sorted_ids = sorted(scores, key=lambda x: -scores[x])[:top_k]
    results = [
        {"file_id": str(meta[i][1]), "filename": meta[i][2], "chunk": meta[i][0]}
        for i in sorted_ids
    ]
    if debug:
        debug_info = [
            {"chunk_id": str(i), "file_id": str(meta[i][1]),
             "filename": meta[i][2], "score": round(scores[i], 6),
             "rank": rank + 1, "fusion_mode": fusion_mode}
            for rank, i in enumerate(sorted_ids)
        ]
        return results, debug_info
    return results


@router.get("/search")
async def search_files(
    q:            str,
    top_k:        int         = 10,
    fusion_mode:  str         = "rrf",
    k_dense:      int         = 20,
    k_sparse:     int         = 20,
    alpha:        float       = 0.5,
    debug:        bool        = False,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query required")
    top_k   = max(1, min(top_k, 50))
    k_dense = max(1, min(k_dense, 100))
    k_sparse = max(1, min(k_sparse, 100))
    alpha   = max(0.0, min(alpha, 1.0))

    if fusion_mode not in ("rrf", "weighted"):
        raise HTTPException(status_code=400, detail="fusion_mode must be 'rrf' or 'weighted'")

    file_q = select(FileModel.id).where(
        FileModel.user_id == current_user.id,
        FileModel.upload_status == "ready",
    )
    file_ids = list((await db.execute(file_q)).scalars().all())

    if not file_ids:
        return []

    query_embedding = await embed(q, input_type="query")
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Embedding failed")

    # Vector search with file metadata + raw similarity
    vec_result = await db.execute(
        select(
            FileChunk.id, FileChunk.content, FileModel.id.label("file_id"), FileModel.filename,
            (1.0 - FileChunk.embedding.cosine_distance(query_embedding)).label("sim")
        )
        .join(FileModel, FileChunk.file_id == FileModel.id)
        .where(FileChunk.file_id.in_(file_ids))
        .where(FileChunk.embedding.isnot(None))
        .order_by(FileChunk.embedding.cosine_distance(query_embedding))
        .limit(k_dense)
    )
    vec_rows = [(r.id, r.content, r.file_id, r.filename, float(r.sim)) for r in vec_result.all()]

    # BM25 search with file metadata + raw rank
    bm25_rows: list[tuple] = []
    try:
        bm25_result = await db.execute(
            select(
                FileChunk.id, FileChunk.content, FileModel.id.label("file_id"), FileModel.filename,
                func.coalesce(
                    func.ts_rank(text("file_chunks.content_tsv"), func.websearch_to_tsquery('simple', text(":q"))),
                    0.0
                ).label("rank")
            )
            .join(FileModel, FileChunk.file_id == FileModel.id)
            .where(FileChunk.file_id.in_(file_ids))
            .where(text("file_chunks.content_tsv @@ websearch_to_tsquery('simple', :q)"))
            .order_by(text("ts_rank(file_chunks.content_tsv, websearch_to_tsquery('simple', :q)) DESC"))
            .limit(k_sparse)
            .params(q=q)
        )
        bm25_rows = [(r.id, r.content, r.file_id, r.filename, float(r.rank)) for r in bm25_result.all()]
    except Exception as e:
        logger.warning("[search] bm25 failed err=%s", e)

    result = _fuse(vec_rows, bm25_rows, top_k, fusion_mode, alpha, k_dense, k_sparse, debug)
    if debug:
        results_list, debug_info = result
        return {"results": results_list, "debug": debug_info}
    return result
