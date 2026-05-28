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
