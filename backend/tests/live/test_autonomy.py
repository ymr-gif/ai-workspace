"""Live: the autonomous/background pipeline, observed end-to-end over HTTP.

Closes BUGS.md V-A1 (insight generation), V-A2 (memory compaction → version),
V-A3 (graph extraction after chat), V-A6 (auto-title). Each drives the real trigger
and polls the result endpoint until the background job (ARQ / inline async task)
lands its side effect. Throwaway users isolate state.

V-A4 (behavior profile) and V-A5 (preferences) have no HTTP surface — verified
separately via DB/ARQ in the run scripts, recorded in BUGS.md.

Marker: live_nim (real model + background workers).
"""
import time
import uuid

import pytest

pytestmark = pytest.mark.live_nim


def _register_login(client, username, password):
    client.post("/auth/register", json={"username": username, "password": password}).raise_for_status()
    tok = client.post("/auth/token", data={"username": username, "password": password})
    tok.raise_for_status()
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


@pytest.fixture
def fresh(client, admin_headers):
    username = f"verify_{uuid.uuid4().hex[:8]}"
    headers = _register_login(client, username, f"pw-{uuid.uuid4().hex[:8]}")
    yield headers
    users = client.get("/admin/users", headers=admin_headers).json()
    uid = next((u["id"] for u in users if u.get("username") == username), None)
    if uid:
        client.patch(f"/admin/users/{uid}/active", headers=admin_headers)


def _chat(sse_post, headers, message, conversation_id=None, timeout=120):
    payload = {"message": message, "stream": True}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    events = sse_post("/chat/stream", headers, payload, timeout=timeout)
    return next((e for e in events if e.get("type") == "done"), None)


def _poll(fn, ok, timeout=90, interval=2.0):
    """Poll fn() until ok(result) or timeout; return last result."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = fn()
        if ok(last):
            return last
        time.sleep(interval)
    return last


# ══════════════════════════════════════════════════════════════════════════════
# V-A3 Graph extraction after chat — Neo4j entities grow
# ══════════════════════════════════════════════════════════════════════════════
def test_graph_extraction_after_chat(client, sse_post, fresh):
    before = client.get("/graph/stats", headers=fresh).json()
    assert before.get("entities") == 0, before

    done = _chat(sse_post, fresh,
                 "My name is Alice Quinn. I work at Acme Robotics on Project Titan with my colleague Bob Stone.")
    assert done is not None

    after = _poll(lambda: client.get("/graph/stats", headers=fresh).json(),
                  lambda s: (s or {}).get("entities", 0) > 0, timeout=90)
    assert after.get("entities", 0) > 0, f"no graph entities extracted after chat: {after}"


# ══════════════════════════════════════════════════════════════════════════════
# V-A6 Auto-title — conversation gets a real title after the 2nd message
# ══════════════════════════════════════════════════════════════════════════════
def test_auto_title_after_second_message(client, sse_post, fresh):
    first_msg = "Let's discuss the quarterly revenue forecast for the hardware division."
    done1 = _chat(sse_post, fresh, first_msg)
    conv = done1["conversation_id"]

    def _title():
        row = next((c for c in client.get("/conversations", headers=fresh).json()
                    if c.get("id") == conv), None)
        return (row or {}).get("title")

    initial = _title()
    # second turn in the SAME conversation triggers _auto_title
    _chat(sse_post, fresh, "What drove the biggest change?", conversation_id=conv)

    final = _poll(_title, lambda t: t and t != initial and t != first_msg and not first_msg.startswith(t or "x"),
                  timeout=60)
    assert final, "no title at all"
    assert final != first_msg, f"title still the raw first message: {final!r}"


# ══════════════════════════════════════════════════════════════════════════════
# V-A2 Memory compaction → UserMemoryVersion snapshot
# ══════════════════════════════════════════════════════════════════════════════
def test_compaction_creates_version(client, fresh):
    # seed a memory sheet worth compacting
    for fact in (
        "I prefer dark mode in all applications.",
        "My primary programming language is Python.",
        "I live in the UTC+8 timezone.",
        "I prefer metric units.",
        "My favorite database is Postgres.",
    ):
        client.post("/memory/write", headers=fresh, json={"fact": fact})

    before = len(client.get("/memory/history", headers=fresh).json())
    comp = client.post("/memory/compact", headers=fresh)
    assert comp.status_code in (200, 202), comp.text

    after = _poll(lambda: client.get("/memory/history", headers=fresh).json(),
                  lambda v: len(v) > before, timeout=90)
    assert len(after) > before, f"compaction created no new memory version (before={before}, after={len(after)})"


# ══════════════════════════════════════════════════════════════════════════════
# V-A1 Insight generation — webhook → process_webhook_job → UserInsight
# ══════════════════════════════════════════════════════════════════════════════
def test_insight_generated_from_webhook(client, fresh):
    token = client.post("/auth/me/webhook-token", headers=fresh).json()["webhook_token"]
    before = len(client.get("/insights", headers=fresh).json())

    ev = client.post(f"/api/webhooks/{token}", json={
        "event_type": "external.data",
        "payload": {"source": "crm", "summary": "Customer Acme upgraded to enterprise tier; renewal in 30 days; champion is Alice Quinn."},
    })
    assert ev.status_code in (200, 201, 202), ev.text

    after = _poll(lambda: client.get("/insights", headers=fresh).json(),
                  lambda ins: len(ins) > before, timeout=120)
    assert len(after) > before, f"webhook produced no UserInsight (before={before}, after={len(after)})"
