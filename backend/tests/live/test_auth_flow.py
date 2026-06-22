"""Live: full auth lifecycle — login, /auth/me, register, API-key issue/use/revoke.

Marker: live_nim.
"""
import uuid

import pytest

pytestmark = pytest.mark.live_nim


def test_seeded_login_and_me(client, user_headers):
    me = client.get("/auth/me", headers=user_headers)
    assert me.status_code == 200
    assert me.json()["username"] == "user"


def test_bad_password_rejected(client):
    r = client.post("/auth/token", data={"username": "user", "password": "wrong"})
    assert r.status_code in (400, 401)


def test_register_then_login(client):
    uname = f"verify_{uuid.uuid4().hex[:10]}"
    r = client.post("/auth/register", json={"username": uname, "password": "pw-secret-123"})
    if r.status_code == 403:
        pytest.skip("registration is invite-gated on this target (REQUIRE_INVITE=true)")
    assert r.status_code in (200, 201), r.text
    # new user can authenticate
    tok = client.post("/auth/token", data={"username": uname, "password": "pw-secret-123"})
    assert tok.status_code == 200
    assert tok.json()["access_token"]


def test_api_key_issue_use_revoke(client):
    """Issue an API key for a throwaway user, prove it authenticates, then revoke it."""
    uname = f"verify_{uuid.uuid4().hex[:10]}"
    reg = client.post("/auth/register", json={"username": uname, "password": "pw-secret-123"})
    if reg.status_code == 403:
        pytest.skip("registration is invite-gated on this target")
    assert reg.status_code in (200, 201), reg.text
    tok = client.post("/auth/token", data={"username": uname, "password": "pw-secret-123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    issued = client.post("/auth/me/api-key", headers=h)
    assert issued.status_code in (200, 201), issued.text
    api_key = issued.json().get("api_key") or issued.json().get("key")
    assert api_key, issued.json()

    # API key authenticates (sent as bearer; security.py falls back to DB key lookup)
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {api_key}"})
    assert me.status_code == 200
    assert me.json()["username"] == uname

    assert client.delete("/auth/me/api-key", headers=h).status_code in (200, 204)
