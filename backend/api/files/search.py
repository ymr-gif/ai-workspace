import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from llm.embeddings import embed
from models import File as FileModel, FileChunk, User

router = APIRouter()
logger = logging.getLogger("files.search")

_RRF_K   = 60
_FETCH_N = 20


@router.get("/search")
async def search_files(
    q:            str,
    workspace_id: str | None  = None,
    top_k:        int         = 10,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query required")
    top_k = max(1, min(top_k, 50))

    file_q = select(FileModel.id).where(
        FileModel.user_id == current_user.id,
        FileModel.upload_status == "ready",
    )
    if workspace_id:
        file_q = file_q.where(FileModel.workspace_id == workspace_id)
    file_ids = list((await db.execute(file_q)).scalars().all())

    if not file_ids:
        return []

    query_embedding = await embed(q, input_type="query")
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Embedding failed")

    # Vector search with file metadata
    vec_result = await db.execute(
        select(FileChunk.id, FileChunk.content, FileModel.id.label("file_id"), FileModel.filename)
        .join(FileModel, FileChunk.file_id == FileModel.id)
        .where(FileChunk.file_id.in_(file_ids))
        .where(FileChunk.embedding.isnot(None))
        .order_by(FileChunk.embedding.cosine_distance(query_embedding))
        .limit(_FETCH_N)
    )
    vec_rows = [(r.id, r.content, r.file_id, r.filename) for r in vec_result.all()]

    # BM25 search with file metadata
    bm25_rows: list[tuple] = []
    try:
        bm25_result = await db.execute(
            select(FileChunk.id, FileChunk.content, FileModel.id.label("file_id"), FileModel.filename)
            .join(FileModel, FileChunk.file_id == FileModel.id)
            .where(FileChunk.file_id.in_(file_ids))
            .where(text("file_chunks.content_tsv @@ websearch_to_tsquery('simple', :q)"))
            .order_by(text("ts_rank(file_chunks.content_tsv, websearch_to_tsquery('simple', :q)) DESC"))
            .limit(_FETCH_N)
            .params(q=q)
        )
        bm25_rows = [(r.id, r.content, r.file_id, r.filename) for r in bm25_result.all()]
    except Exception as e:
        logger.warning("[search] bm25 failed err=%s", e)

    # RRF merge preserving file metadata
    scores: dict = {}
    meta:   dict = {}
    for rank, (cid, content, file_id, filename) in enumerate(vec_rows):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        meta[cid]   = (content, file_id, filename)
    for rank, (cid, content, file_id, filename) in enumerate(bm25_rows):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        meta[cid]   = (content, file_id, filename)

    sorted_ids = sorted(scores, key=lambda x: -scores[x])[:top_k]
    return [
        {"file_id": str(meta[i][1]), "filename": meta[i][2], "chunk": meta[i][0]}
        for i in sorted_ids
    ]
