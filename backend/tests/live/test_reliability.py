"""Live: reliability invariants — rate limiting + cost cap.

Closes BUGS.md V-D3 (rate limit) and V-D4 (cost cap). Both run on **throwaway users**
so the blast radius (a locked-out / capped user) never touches real or seeded accounts.

V-D1 (fallback chain) and V-D2 (circuit breaker) require tripping a model's breaker in
Redis — done as an isolated, immediately-reverted run-script step (recorded in BUGS.md),
not here, to avoid leaving breaker state across the test session.

Note: cost accounting is eventually-consistent (cost is persisted by a background task
after the reply), so the cost-cap test waits for the first turn's cost to register before
capping — otherwise the cap check reads a stale $0 spend.

Marker: live_nim.
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


def _uid(client, admin_headers, username):
    return next((u["id"] for u in client.get("/admin/users", headers=admin_headers).json()
                 if u.get("username") == username), None)


@pytest.fixture
def fresh(client, admin_headers):
    username = f"verify_{uuid.uuid4().hex[:8]}"
    headers = _register_login(client, username, f"pw-{uuid.uuid4().hex[:8]}")
    uid = _uid(client, admin_headers, username)
    yield {"headers": headers, "uid": uid, "username": username}
    if uid:
        client.patch(f"/admin/users/{uid}/active", headers=admin_headers)


# ══════════════════════════════════════════════════════════════════════════════
# V-D3 Rate limiting — chat 15 / 60s per user → 429 (isolated to a throwaway user)
# ══════════════════════════════════════════════════════════════════════════════
def test_rate_limit_returns_429(client, fresh):
    h = fresh["headers"]
    codes = []
    # fire >15 quickly; the limiter rejects (429) before inference once the window fills
    for _ in range(20):
        r = client.post("/chat", headers=h, json={"message": "hi"}, timeout=60)
        codes.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in codes, f"rate limit never tripped after {len(codes)} requests: {codes}"


# ══════════════════════════════════════════════════════════════════════════════
# V-D4 Cost cap — rolling window exceeded → 402 (isolated to a throwaway user)
# ══════════════════════════════════════════════════════════════════════════════
def test_cost_cap_returns_402(client, admin_headers, fresh):
    """Cost cap is enforced on the **stream** path (the stateful one). Set a near-zero
    cap, then stream unique prompts until accrued cost registers (async) and the
    pre-flight check returns 402. (Note: nonstream POST /chat is stateless — no cost
    accounting — so the cap does not apply there; tracked as BUG-V3.)"""
    h = fresh["headers"]
    uid = fresh["uid"]
    assert uid, "could not resolve throwaway uid"

    set_limit = client.patch(f"/admin/users/{uid}/cost-limit", headers=admin_headers,
                             json={"cost_limit_usd": 0.0000001, "cost_window_days": 30})
    assert set_limit.status_code == 200, set_limit.text
    try:
        got_402 = False
        body = ""
        for _ in range(8):
            r = client.post("/chat/stream", headers=h,
                            json={"message": f"Describe gadget {uuid.uuid4().hex[:8]} briefly.", "stream": True},
                            timeout=90)
            if r.status_code == 402:
                got_402 = True
                body = r.text
                break
            time.sleep(3)  # let the previous turn's cost persist
        assert got_402, "cost cap never returned 402 after accruing cost on the stream path"
        assert "cost cap" in body.lower() or "/" in body, body[:200]
    finally:
        client.patch(f"/admin/users/{uid}/cost-limit", headers=admin_headers,
                     json={"cost_limit_usd": None})
