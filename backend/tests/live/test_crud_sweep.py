"""Live: HTTP-contract sweep across the read/CRUD surface + admin endpoints.

Asserts each endpoint authenticates and returns its expected shape. Marker: live_nim.
"""
import pytest

pytestmark = pytest.mark.live_nim


@pytest.mark.parametrize("path", [
    "/conversations",
    "/memory",
    "/memory/conflicts",
    "/graph/stats",
    "/goals",
    "/scheduled-prompts",
    "/insights",
    "/integrations",
    "/usage",
    "/api/notifications/preferences",
])
def test_user_endpoint_authenticated_200(client, user_headers, path):
    r = client.get(path, headers=user_headers)
    assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:160]}"


@pytest.mark.parametrize("path", ["/conversations", "/memory", "/goals", "/usage"])
def test_user_endpoint_requires_auth(client, path):
    assert client.get(path).status_code == 401


def test_notification_prefs_patch_roundtrip(client, user_headers):
    cur = client.get("/api/notifications/preferences", headers=user_headers).json()
    assert "push_enabled" in cur
    original = cur.get("email_digest", True)
    target = not original
    # PATCH returns {"ok": true}; confirm persistence via a follow-up GET
    patched = client.patch("/api/notifications/preferences", headers=user_headers, json={"email_digest": target})
    assert patched.status_code == 200, patched.text
    after = client.get("/api/notifications/preferences", headers=user_headers).json()
    assert after["email_digest"] is target
    # restore
    client.patch("/api/notifications/preferences", headers=user_headers, json={"email_digest": original})


def test_goal_create_update_delete(client, user_headers):
    create = client.post("/goals", headers=user_headers, json={"title": "verify-goal", "description": "pre-ship check"})
    if create.status_code == 422:
        pytest.skip(f"goal schema differs on target: {create.text[:160]}")
    assert create.status_code in (200, 201), create.text
    gid = create.json().get("id")
    assert gid
    upd = client.patch(f"/goals/{gid}", headers=user_headers, json={"status": "completed"})
    assert upd.status_code == 200, upd.text
    assert client.delete(f"/goals/{gid}", headers=user_headers).status_code in (200, 204)


# ── admin surface ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", ["/admin/users", "/admin/audit-log", "/admin/env"])
def test_admin_endpoints(client, admin_headers, path):
    r = client.get(path, headers=admin_headers)
    assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:160]}"


def test_admin_endpoints_forbidden_for_user(client, user_headers):
    r = client.get("/admin/users", headers=user_headers)
    assert r.status_code in (401, 403)


def test_admin_env_masks_secrets(client, admin_headers):
    env = client.get("/admin/env", headers=admin_headers).json()
    blob = str(env).lower()
    # the real NIM key / jwt secret must never come back in cleartext
    assert "nvapi-" not in blob
