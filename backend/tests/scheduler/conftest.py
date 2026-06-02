"""Fixtures for scheduler_worker tests.

Importing services.scheduler_worker pulls in apscheduler, which is present in the
scheduler container but not on the host — so every test here is guarded by
`pytest.importorskip("apscheduler")` and skips cleanly where it is absent.
No live Postgres: AsyncSessionLocal is monkeypatched per-test.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
