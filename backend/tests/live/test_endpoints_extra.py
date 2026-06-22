"""Live: HTTP-contract coverage for endpoints the earlier sweeps never touched.

Closes BUGS.md V-C1..C4, V-C6, V-D5, V-E5, V-B1 against the running stack. Mutating
tests isolate blast radius with **throwaway users** (registered per-test, disabled in
teardown — there is no user-delete endpoint) and always restore any shared state.

Marker: live_nim (several create a conversation via a real chat turn).
"""
import time
import uuid

import pytest

pytestmark = pytest.mark.live_nim


# ── throwaway-user helpers ──────────────────────────────────────────────────────
def _register_login(client, username, password):
    r = client.post("/auth/register", json={"username": username, "password": password})
    assert r.status_code in (200, 201), r.text
    tok = client.post("/auth/token", data={"username": username, "password": password})
    tok.raise_for_status()
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


def _uid_of(client, admin_headers, username):
    users = client.get("/admin/users", headers=admin_headers).json()
    row = next((u for u in users if u.get("username") == username), None)
    return (row or {}).get("id")


@pytest.fixture
def throwaway(client, admin_headers):
    """A fresh isolated user. Yields {headers, username, uid}. Disabled in teardown."""
    username = f"verify_{uuid.uuid4().hex[:8]}"
    password = f"pw-{uuid.uuid4().hex[:10]}"
    headers = _register_login(client, username, password)
    uid = _uid_of(client, admin_headers, username)
    yield {"headers": headers, "username": username, "uid": uid, "password": password}
    # no delete endpoint → disable so the row is inert
    if uid:
        client.patch(f"/admin/users/{uid}/active", headers=admin_headers)


def _new_conversation(sse_post, headers, msg="Say hi in one word."):
    """Create a conversation via one cheap chat turn; return its id."""
    events = sse_post("/chat/stream", headers, {"message": msg, "stream": True}, timeout=90)
    done = next((e for e in events if e.get("type") == "done"), None)
    assert done and done.get("conversation_id"), "no conversation_id from chat"
    return done["conversation_id"]


# ══════════════════════════════════════════════════════════════════════════════
# V-C1 Prompt templates — full CRUD + apply
# ══════════════════════════════════════════════════════════════════════════════
def test_templates_crud_and_apply(client, sse_post, throwaway):
    h = throwaway["headers"]
    name = f"tmpl-{uuid.uuid4().hex[:6]}"
    create = client.post("/templates", headers=h,
                         json={"name": name, "description": "verify", "content": "You are a pirate."})
    assert create.status_code in (200, 201), create.text
    tid = create.json()["id"]

    got = client.get(f"/templates/{tid}", headers=h)
    assert got.status_code == 200 and got.json()["name"] == name

    listing = client.get("/templates", headers=h).json()
    assert any(t["id"] == tid for t in listing)

    upd = client.put(f"/templates/{tid}", headers=h,
                     json={"name": name, "content": "You are a ninja."})
    assert upd.status_code == 200, upd.text
    assert "ninja" in client.get(f"/templates/{tid}", headers=h).json()["content"]

    # apply to a real conversation
    conv = _new_conversation(sse_post, h)
    applied = client.post(f"/templates/{tid}/apply/{conv}", headers=h)
    assert applied.status_code in (200, 201), applied.text

    assert client.delete(f"/templates/{tid}", headers=h).status_code in (200, 204)
    assert client.get(f"/templates/{tid}", headers=h).status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# V-C2 Export — read-only; test on the seeded user (has data)
# ══════════════════════════════════════════════════════════════════════════════
def test_export_full_zip(client, user_headers):
    with client.stream("GET", "/export/full", headers=user_headers, timeout=60) as r:
        assert r.status_code == 200, r.text
        assert "zip" in r.headers.get("content-type", "").lower()
        body = b"".join(r.iter_bytes())
    assert body[:2] == b"PK", "not a valid zip (no PK magic)"
    assert len(body) > 100, f"export suspiciously small: {len(body)} bytes"


# ══════════════════════════════════════════════════════════════════════════════
# V-C3 Unified search — shape + finds freshly written memory
# ══════════════════════════════════════════════════════════════════════════════
def test_unified_search_shape(client, user_headers):
    r = client.get("/search", headers=user_headers, params={"q": "project"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"query", "results"}, body
    assert isinstance(body["results"], list)


def test_unified_search_finds_memory(client, throwaway):
    h = throwaway["headers"]
    token = uuid.uuid4().hex[:8].upper()
    client.post("/memory/write", headers=h, json={"fact": f"The verification codeword is {token}."})
    # memory write is immediate; search should surface it
    found = False
    for _ in range(5):
        res = client.get("/search", headers=h, params={"q": token}).json().get("results", [])
        if any(token in (str(x.get("snippet", "")) + str(x.get("title", ""))) for x in res):
            found = True
            break
        time.sleep(1.0)
    assert found, f"freshly written memory '{token}' not found by /search"


# ══════════════════════════════════════════════════════════════════════════════
# V-C4 Conversation ops — patch / export / search / delete + file attach-detach
# ══════════════════════════════════════════════════════════════════════════════
def test_conversation_patch_export_search_delete(client, sse_post, throwaway):
    h = throwaway["headers"]
    conv = _new_conversation(sse_post, h, "Remember the keyword BANANA.")

    patched = client.patch(f"/conversations/{conv}", headers=h, json={"system_prompt": "Be terse."})
    assert patched.status_code == 200, patched.text

    for fmt in ("markdown", "json"):
        ex = client.get(f"/conversations/{conv}/export", headers=h, params={"format": fmt})
        assert ex.status_code == 200, f"{fmt} export: {ex.text[:160]}"

    listed = client.get("/conversations", headers=h, params={"q": "BANANA"}).json()
    assert isinstance(listed, list)

    assert client.delete(f"/conversations/{conv}", headers=h).status_code in (200, 204)
    assert all(c.get("id") != conv for c in client.get("/conversations", headers=h).json())


def test_conversation_file_attach_detach(client, sse_post, throwaway):
    h = throwaway["headers"]
    conv = _new_conversation(sse_post, h)
    up = client.post("/files/upload", headers=h,
                     files={"file": (f"att_{uuid.uuid4().hex[:6]}.txt", b"attach me", "text/plain")})
    assert up.status_code in (200, 201), up.text
    fid = up.json().get("id") or up.json().get("file_id")

    att = client.post(f"/conversations/{conv}/files", headers=h, json={"file_id": str(fid)})
    assert att.status_code in (200, 201), att.text
    assert any(str(f.get("id")) == str(fid) for f in client.get(f"/conversations/{conv}/files", headers=h).json())

    det = client.delete(f"/conversations/{conv}/files/{fid}", headers=h)
    assert det.status_code in (200, 204), det.text
    client.delete(f"/files/{fid}", headers=h)
    client.delete(f"/conversations/{conv}", headers=h)


# ══════════════════════════════════════════════════════════════════════════════
# V-C6 Invite gate — admin issues, register consumes
# ══════════════════════════════════════════════════════════════════════════════
def test_invite_issue_and_consume(client, admin_headers):
    issued = client.post("/auth/invite", headers=admin_headers)
    assert issued.status_code in (200, 201), issued.text
    token = issued.json().get("token")
    assert token, issued.json()

    prefix = token[:8]
    invites = client.get("/auth/invites", headers=admin_headers).json()
    assert any(str(i.get("token_prefix", i.get("token", "")))[:8] == prefix for i in invites), invites

    # Register WITH the token must work. (Consumption-enforcement — reusing a spent
    # token / blocking token-less register — only applies when REQUIRE_INVITE=true,
    # which is exercised in test_reliability.py under a temporary env flip.)
    uname = f"verify_inv_{uuid.uuid4().hex[:6]}"
    reg = client.post("/auth/register", json={"username": uname, "password": "pw-invite-123", "invite_token": token})
    assert reg.status_code in (200, 201), reg.text
    # tidy: disable the created user
    uid = _uid_of(client, admin_headers, uname)
    if uid:
        client.patch(f"/admin/users/{uid}/active", headers=admin_headers)


# ══════════════════════════════════════════════════════════════════════════════
# V-D5 Memory conflicts — write contradictions, scan, resolve
# ══════════════════════════════════════════════════════════════════════════════
def test_memory_conflict_scan_resolve(client, throwaway):
    h = throwaway["headers"]
    client.post("/memory/write", headers=h, json={"fact": "My favorite color is blue."})
    client.post("/memory/write", headers=h, json={"fact": "My favorite color is red."})
    scan = client.post("/memory/conflicts/scan", headers=h)
    assert scan.status_code == 200, scan.text
    # detection is LLM-driven; may or may not flag. If flagged, resolve must work.
    conflicts = client.get("/memory/conflicts", headers=h).json()
    if conflicts:
        cid = conflicts[0]["id"]
        res = client.post(f"/memory/conflicts/{cid}/resolve", headers=h, json={"strategy": "keep_a"})
        assert res.status_code == 200, res.text
    else:
        pytest.skip("conflict scan flagged none (LLM judgement) — scan endpoint still 200")


# ══════════════════════════════════════════════════════════════════════════════
# V-E5 Re-embed — admin trigger accepted
# ══════════════════════════════════════════════════════════════════════════════
def test_re_embed_accepted(client, admin_headers):
    r = client.post("/admin/re-embed", headers=admin_headers)
    assert r.status_code in (200, 202), r.text


# ══════════════════════════════════════════════════════════════════════════════
# V-B1 Scheduled prompts — create → run → run recorded → delete
# ══════════════════════════════════════════════════════════════════════════════
def test_scheduled_prompt_create_run_delete(client, throwaway):
    h = throwaway["headers"]
    create = client.post("/scheduled-prompts", headers=h,
                         json={"name": "verify-sched", "prompt": "Say the word PONG.", "schedule": "daily"})
    assert create.status_code in (200, 201), create.text
    sid = create.json()["id"]
    assert create.json().get("cron_expr"), "schedule alias did not resolve to a cron_expr"

    run = client.post(f"/scheduled-prompts/{sid}/run", headers=h)
    assert run.status_code in (200, 201, 202), run.text

    # execution is async — poll the runs list for a terminal status
    status = None
    for _ in range(90):
        runs = client.get(f"/scheduled-prompts/{sid}/runs", headers=h).json()
        if runs:
            status = runs[0].get("status")
            if status in ("completed", "error", "success", "done"):
                break
        time.sleep(1.0)
    assert status is not None, "no ScheduledPromptRun recorded after /run"
    assert client.delete(f"/scheduled-prompts/{sid}", headers=h).status_code in (200, 204)
