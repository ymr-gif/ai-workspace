from fastapi import APIRouter, Depends

from auth.security import get_current_user
from models import User

router = APIRouter(prefix="/graph", tags=["graph"])


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
async def graph_sample(current_user: User = Depends(get_current_user)):
    from core.neo4j_client import get_driver

    driver = get_driver()
    if not driver:
        return {"available": False, "triples": []}

    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (a:Entity {user_id: $uid})-[r:RELATED_TO]->(b:Entity {user_id: $uid}) "
                "RETURN a.name AS source, r.type AS relation, b.name AS target "
                "ORDER BY random() LIMIT 10",
                uid=current_user.id,
            )
            rows = await result.data()
            return {
                "available": True,
                "triples": [
                    {"source": row["source"], "relation": row["relation"], "target": row["target"]}
                    for row in rows
                ],
            }
    except Exception:
        return {"available": False, "triples": []}
