import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from llm.embeddings import embed
from models import Conversation, File as FileModel, FileChunk, Message, User, UserMemory

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger("search")

SCOPES = frozenset({"all", "files", "conversations", "memory", "graph"})


async def _search_files(
    db: AsyncSession,
    user_id: int,
    query_embedding: list[float],
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    try:
        file_ids_q = select(FileModel.id).where(
            FileModel.user_id == user_id,
            FileModel.upload_status == "ready",
        )
        file_ids = list((await db.execute(file_ids_q)).scalars().all())
        if not file_ids:
            return []

        vec_result = await db.execute(
            select(
                FileChunk.id,
                FileChunk.content,
                FileModel.id,
                FileModel.filename,
                (1.0 - FileChunk.embedding.cosine_distance(query_embedding)).label("sim"),
            )
            .join(FileModel, FileChunk.file_id == FileModel.id)
            .where(FileChunk.file_id.in_(file_ids))
            .where(FileChunk.embedding.isnot(None))
            .order_by(FileChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k),
        )
        return [
            {
                "source": "files",
                "score": round(float(row.sim), 4),
                "title": row.filename,
                "snippet": row.content[:300],
                "id": str(row.file_id),
            }
            for row in vec_result.all()
        ]
    except Exception as e:
        logger.warning("_search_files failed: %s", e)
        return []


async def _search_conversations(
    db: AsyncSession,
    user_id: int,
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    try:
        if not query_text.strip():
            return []

        result = await db.execute(
            select(
                Conversation.id,
                Conversation.title,
                Message.content,
                func.ts_rank(
                    text("messages.content_tsv"),
                    func.websearch_to_tsquery("simple", text(":q")),
                ).label("rank"),
            )
            .join(Message, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
            .where(text("messages.content_tsv @@ websearch_to_tsquery('simple', :q)"))
            .order_by(
                text("ts_rank(messages.content_tsv, websearch_to_tsquery('simple', :q)) DESC")
            )
            .limit(top_k)
            .params(q=query_text),
        )
        return [
            {
                "source": "conversations",
                "score": round(float(row.rank), 4),
                "title": row.title,
                "snippet": row.content[:300],
                "id": str(row.id),
            }
            for row in result.all()
        ]
    except Exception as e:
        logger.warning("_search_conversations failed: %s", e)
        return []


async def _search_memory(
    db: AsyncSession,
    user_id: int,
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    try:
        lower = query_text.lower().strip()
        if not lower:
            return []

        result = await db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        memory = result.scalar_one_or_none()
        if not memory or not memory.content:
            return []

        fact_saliences = memory.fact_saliences or {}
        out = []
        for line in memory.content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if lower in line.lower():
                out.append({
                    "source": "memory",
                    "score": round(fact_saliences.get(line, 1.0), 4),
                    "title": "Memory Fact",
                    "snippet": line[:300],
                    "id": f"memory-{user_id}",
                })
                if len(out) >= top_k:
                    break
        return out
    except Exception as e:
        logger.warning("_search_memory failed: %s", e)
        return []


async def _search_graph(
    user_id: int,
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    try:
        from core.neo4j_client import get_driver

        driver = get_driver()
        if not driver:
            return []

        words = [w for w in query_text.split() if len(w) > 2]
        if not words:
            return []

        ft_query = " ".join(words)
        async with driver.session() as session:
            result = await session.run(
                "CALL db.index.fulltext.queryNodes('entity_name_ft', $ft) YIELD node AS e, score "
                "WHERE e.user_id = $uid "
                "OPTIONAL MATCH (e)-[r:RELATED_TO]->() "
                "WITH e, score, count(r) AS rel_count "
                "RETURN e.name AS name, e.type AS type, score, rel_count "
                "ORDER BY score DESC LIMIT $limit",
                uid=user_id,
                ft=ft_query,
                limit=top_k,
            )
            rows = await result.data()
            return [
                {
                    "source": "graph",
                    "score": round(float(row.get("score", 0)), 4),
                    "title": f"{row['name']} ({row['type']})",
                    "snippet": f"Relations: {row.get('rel_count', 0)}",
                    "id": row["name"],
                }
                for row in rows
            ]
    except Exception as e:
        logger.warning("_search_graph failed: %s", e)
        return []


@router.get("")
async def unified_search(
    q: str,
    scope: str = "all",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query required")
    if scope not in SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scope: {scope}. Must be one of: {', '.join(sorted(SCOPES))}",
        )

    query_text = q.strip()

    coros: list = []
    coro_names: list[str] = []

    if scope in ("all", "files"):
        query_embedding = await embed(query_text, input_type="query")
        if query_embedding:
            coros.append(_search_files(db, current_user.id, query_embedding, query_text))
            coro_names.append("files")

    if scope in ("all", "conversations"):
        coros.append(_search_conversations(db, current_user.id, query_text))
        coro_names.append("conversations")

    if scope in ("all", "memory"):
        coros.append(_search_memory(db, current_user.id, query_text))
        coro_names.append("memory")

    if scope in ("all", "graph"):
        coros.append(_search_graph(current_user.id, query_text))
        coro_names.append("graph")

    results: list[dict] = []
    if coros:
        gathered = await asyncio.gather(*coros)
        for name, res in zip(coro_names, gathered):
            results.extend(res)

    results.sort(key=lambda r: -r["score"])

    return {"query": query_text, "scope": scope, "results": results}
