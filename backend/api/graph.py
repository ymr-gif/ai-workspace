import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth.security import get_current_user
from models import User

router = APIRouter(prefix="/graph", tags=["graph"])
logger = logging.getLogger("graph")


@router.get("/stats")
async def graph_stats(current_user: User = Depends(get_current_user)):
    from core.neo4j_client import get_driver

    driver = get_driver()
    if not driver:
        return {"available": False, "entities": 0, "relations": 0}

    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity {user_id: $uid}) WITH count(e) AS entities "
                "OPTIONAL MATCH (a:Entity {user_id: $uid})-[r:RELATED_TO]->() "
                "RETURN entities, count(r) AS relations",
                uid=current_user.id,
            )
            row = await result.single()
            return {
                "available": True,
                "entities":  int(row["entities"]  if row else 0),
                "relations": int(row["relations"] if row else 0),
            }
    except Exception:
        return {"available": False, "entities": 0, "relations": 0}


@router.get("/health")
async def graph_health():
    from core.neo4j_client import get_health
    return await get_health()


@router.get("/sample")
async def graph_sample(
    limit: int = 50,
    entity_type: str | None = None,
    current_user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 200))
    from core.neo4j_client import get_driver

    driver = get_driver()
    if not driver:
        return {"available": False, "triples": []}

    try:
        query = (
            "MATCH (a:Entity {user_id: $uid})-[r:RELATED_TO]->(b:Entity {user_id: $uid}) "
        )
        params: dict = {"uid": current_user.id, "limit": limit}
        if entity_type:
            query += "WHERE a.type = $etype "
            params["etype"] = entity_type
        query += "RETURN a.name AS source, r.type AS relation, b.name AS target "
        query += "ORDER BY random() LIMIT $limit"

        async with driver.session() as session:
            result = await session.run(query, **params)
            rows = await result.data()
            return {
                "available": True,
                "triples": [
                    {"source": row["source"], "relation": row["relation"], "target": row["target"]}
                    for row in rows
                ],
            }
    except Exception:
        logger.exception("[graph] sample failed")
        return {"available": False, "triples": []}


@router.delete("/entities/{name}")
async def delete_entity(name: str, current_user: User = Depends(get_current_user)):
    from core.neo4j_client import get_driver
    from llm.graph_memory import _cache_del_user

    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Graph unavailable")

    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:Entity {user_id: $uid, name: $name}) DETACH DELETE n",
            uid=current_user.id, name=name,
        )
        summary = await result.consume()

    await _cache_del_user(current_user.id)
    deleted = summary.counters.nodes_deleted
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    logger.info("[graph] deleted entity=%r user=%d", name, current_user.id)
    return {"deleted": deleted}


@router.post("/prune")
async def prune_graph(current_user: User = Depends(get_current_user)):
    from core.neo4j_client import get_driver
    from llm.graph_memory import _MAX_ENTITY_NAME_LEN, _cache_del_user

    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Graph unavailable")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:Entity {user_id: $uid}) "
            "WHERE size(n.name) > $max_len "
            "   OR (n.type = 'OTHER' AND n.updated_at < $cutoff) "
            "DETACH DELETE n",
            uid=current_user.id, max_len=_MAX_ENTITY_NAME_LEN, cutoff=cutoff,
        )
        summary = await result.consume()

    await _cache_del_user(current_user.id)
    deleted = summary.counters.nodes_deleted
    logger.info("[graph] pruned %d entities user=%d", deleted, current_user.id)
    return {"pruned": deleted}
