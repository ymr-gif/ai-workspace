"""Live: health, metrics, auth gating against a running stack.

Marker: live_nim (auto-skipped unless RUN_LIVE_NIM=1 + VERIFY_BASE_URL reachable).
"""
import pytest

pytestmark = pytest.mark.live_nim


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    checks = body["checks"]
    # core dependencies must report ok on a launch-ready stack
    for dep in ("nim", "embedding", "redis", "db"):
        assert checks[dep]["status"] == "ok", f"{dep} unhealthy: {checks[dep]}"
        assert isinstance(checks[dep]["latency_ms"], (int, float))


def test_metrics_exposed(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "# HELP" in r.text or "# TYPE" in r.text


def test_unauthenticated_is_401(client):
    assert client.get("/conversations").status_code == 401
    assert client.get("/memory").status_code == 401


def test_models_listed_in_health(client):
    body = client.get("/health").json()
    assert set(body["models"]) >= {"llama", "coder", "reasoning"}
