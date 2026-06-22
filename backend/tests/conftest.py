"""Top-level test config: env defaults, marker gating, shared fixtures.

Tiers (see pytest.ini markers):
  unit      — default, no external deps. Runs by default.
  infra     — direct Postgres/Redis/Neo4j. Opt-in via RUN_INFRA=1.
  live_nim  — HTTP against a running stack + live model. Opt-in via RUN_LIVE_NIM=1
              and a reachable VERIFY_BASE_URL (default http://localhost:8000).
  optional  — gated optional features; each test self-skips on missing creds.

Gating is automatic: an opt-in tier with its prerequisite unmet is *skipped*, never
failed, so a plain `pytest` stays green on a laptop while CI/operators flip the env
flags to exercise the heavier tiers.
"""
import os
import sys

import pytest

# backend/ on sys.path so `import config`, `import api...` resolve (mirrors existing tests).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Minimal env so importing `config` never explodes during unit collection.
os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

BASE_URL = os.getenv("VERIFY_BASE_URL", "http://localhost:8000").rstrip("/")
SEED_USER = (os.getenv("VERIFY_USER", "user"), os.getenv("VERIFY_USER_PW", "user-secret"))
SEED_ADMIN = (os.getenv("VERIFY_ADMIN", "admin"), os.getenv("VERIFY_ADMIN_PW", "admin-secret"))


# ── reachability probe (cached once per session) ────────────────────────────────
_REACHABLE = None


def _stack_reachable() -> bool:
    global _REACHABLE
    if _REACHABLE is None:
        try:
            import httpx

            r = httpx.get(f"{BASE_URL}/health", timeout=8)
            _REACHABLE = r.status_code == 200
        except Exception:
            _REACHABLE = False
    return _REACHABLE


def pytest_collection_modifyitems(config, items):
    """Auto-skip opt-in tiers whose prerequisites are unmet (never fail them)."""
    run_infra = os.getenv("RUN_INFRA", "").lower() in ("1", "true", "yes")
    run_live = os.getenv("RUN_LIVE_NIM", "").lower() in ("1", "true", "yes")

    skip_infra = pytest.mark.skip(reason="infra tier off (set RUN_INFRA=1 with Postgres/Redis/Neo4j reachable)")
    skip_live = pytest.mark.skip(reason="live tier off (set RUN_LIVE_NIM=1 with VERIFY_BASE_URL reachable)")
    skip_unreach = pytest.mark.skip(reason=f"stack not reachable at {BASE_URL}/health")

    for item in items:
        if "infra" in item.keywords and not run_infra:
            item.add_marker(skip_infra)
        if "live_nim" in item.keywords or "optional" in item.keywords:
            if not run_live:
                item.add_marker(skip_live)
            elif not _stack_reachable():
                item.add_marker(skip_unreach)


# ── shared fixtures for HTTP-driven (live/optional) tests ───────────────────────
@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def client(base_url):
    """A plain httpx.Client pointed at the running stack."""
    import httpx

    with httpx.Client(base_url=base_url, timeout=60) as c:
        yield c


def _login(client, username, password) -> str:
    r = client.post("/auth/token", data={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def user_token(client) -> str:
    return _login(client, *SEED_USER)


@pytest.fixture(scope="session")
def admin_token(client) -> str:
    return _login(client, *SEED_ADMIN)


@pytest.fixture
def user_headers(user_token) -> dict:
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def sse_post(client):
    """POST and return the parsed list of SSE events (each a dict).

    Usage: events = sse_post("/chat/stream", headers, {"message": "..."})
    """
    import json

    def _do(path: str, headers: dict, payload: dict, timeout: int = 90):
        events = []
        with client.stream("POST", path, headers=headers, json=payload, timeout=timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[len("data:"):].strip()
                try:
                    events.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
        return events

    return _do
