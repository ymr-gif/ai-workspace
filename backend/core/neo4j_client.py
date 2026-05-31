import logging

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

logger = logging.getLogger("neo4j_client")

_driver = None


async def init_neo4j() -> None:
    global _driver
    if not NEO4J_PASSWORD:
        logger.info("[neo4j] NEO4J_PASSWORD not set, graph memory disabled")
        return

    from neo4j import AsyncGraphDatabase

    _driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        max_connection_pool_size=20,
        connection_timeout=5.0,
        max_transaction_retry_time=15.0,
    )
    await _driver.verify_connectivity()

    async with _driver.session() as session:
        await session.run(
            "CREATE CONSTRAINT entity_key IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE (e.user_id, e.name) IS UNIQUE"
        )
        await session.run(
            "CREATE FULLTEXT INDEX entity_name_ft IF NOT EXISTS "
            "FOR (e:Entity) ON EACH [e.name]"
        )
        await session.run(
            "CREATE INDEX entity_user_id IF NOT EXISTS "
            "FOR (e:Entity) ON (e.user_id)"
        )
        await session.run(
            "CREATE INDEX canvas_user_id IF NOT EXISTS "
            "FOR (n:CanvasNode) ON (n.user_id)"
        )

    logger.info("[neo4j] connected to %s", NEO4J_URI)


async def close_neo4j() -> None:
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


def get_driver():
    return _driver


async def get_health() -> dict:
    driver = get_driver()
    if not driver:
        return {"available": False, "entity_count": 0, "relation_count": 0}

    try:
        from neo4j.exceptions import ServiceUnavailable

        async with driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity) WITH count(e) AS ec "
                "MATCH ()-[r:RELATED_TO]->() RETURN ec, count(r) AS rc"
            )
            row = await result.single()
            return {
                "available": True,
                "entity_count": int(row["ec"]) if row else 0,
                "relation_count": int(row["rc"]) if row else 0,
            }
    except ServiceUnavailable:
        return {"available": False, "entity_count": 0, "relation_count": 0}
