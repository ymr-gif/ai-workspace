"""Fixtures for the infra tier — direct Postgres/Redis/Neo4j connections.

Each fixture self-skips when its backing service is unreachable, so the suite runs
cleanly in CI (all services present) and on a laptop hitting only what's published.
"""
import os

import pytest


def _pg_dsn() -> str:
    # config default is the asyncpg URL; asyncpg.connect wants a plain postgres DSN
    url = os.environ.get("DATABASE_URL", "postgresql://u:p@localhost/db")
    return url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture(scope="session")
def db_dsn():
    import asyncio

    import asyncpg

    dsn = _pg_dsn()

    async def _probe():
        conn = await asyncpg.connect(dsn, timeout=5)
        await conn.close()

    try:
        asyncio.get_event_loop().run_until_complete(_probe())
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable at DATABASE_URL: {e}")
    return dsn


@pytest.fixture(scope="session")
def redis_url():
    import asyncio

    import redis.asyncio as aioredis

    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    async def _probe():
        r = aioredis.from_url(url)
        await r.ping()
        await r.aclose()

    try:
        asyncio.get_event_loop().run_until_complete(_probe())
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redis not reachable at REDIS_URL: {e}")
    return url


@pytest.fixture(scope="session")
def neo4j_conn():
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        pytest.skip("NEO4J_URI not set")
    from neo4j import GraphDatabase

    user = os.environ.get("NEO4J_USER", "neo4j")
    pw = os.environ.get("NEO4J_PASSWORD", "changeme")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pw))
        driver.verify_connectivity()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Neo4j not reachable at NEO4J_URI: {e}")
    yield driver
    driver.close()
