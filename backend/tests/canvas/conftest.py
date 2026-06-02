"""Fixtures for canvas CRUD / hardening tests.

No live Neo4j or Postgres — `get_driver` is replaced with an in-memory fake and
the Postgres session is a MagicMock. Mirrors tests/retrieval/conftest.py setup.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from unittest.mock import MagicMock


class FakeResult:
    """Stand-in for a Neo4j result object."""
    def __init__(self, records=None, nodes_deleted=0, contains_updates=False):
        self._records = records or []
        self._nodes_deleted = nodes_deleted
        self._contains_updates = contains_updates

    async def single(self):
        return self._records[0] if self._records else None

    async def data(self):
        return self._records

    async def consume(self):
        m = MagicMock()
        m.counters = MagicMock(
            nodes_deleted=self._nodes_deleted,
            contains_updates=self._contains_updates,
        )
        return m


class FakeSession:
    def __init__(self, handler):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def run(self, query, **params):
        return self._handler(query, params)


class FakeDriver:
    """driver.session() → FakeSession; `handler(query, params)` returns a FakeResult."""
    def __init__(self, handler):
        self._handler = handler

    def session(self):
        return FakeSession(self._handler)


def make_driver(handler):
    return FakeDriver(handler)
