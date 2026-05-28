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

    _driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
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
            e_result = await session.run("MATCH (e:Entity) RETURN count(e) AS cnt")
            r_result = await session.run("MATCH ()-[r:RELATED_TO]->() RETURN count(r) AS cnt")
            e_row = await e_result.single()
            r_row = await r_result.single()
            return {
                "available": True,
                "entity_count": int(e_row["cnt"]) if e_row else 0,
                "relation_count": int(r_row["cnt"]) if r_row else 0,
            }
    except ServiceUnavailable:
        return {"available": False, "entity_count": 0, "relation_count": 0}
