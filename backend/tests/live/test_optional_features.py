"""Live: optional/gated features — web search, voice, webhooks, push, OAuth start.

Marker: optional (runs only with RUN_LIVE_NIM=1 + reachable stack). Each test further
self-skips when its feature flag/creds are off on the target, so a partial deployment
still passes cleanly.
"""
import uuid

import pytest

pytestmark = pytest.mark.optional


def test_web_search_when_enabled(sse_post, user_headers):
    events = sse_post(
        "/chat/stream",
        user_headers,
        {"message": "What is the latest news today? Search the web."},
        timeout=120,
    )
    done = next((e for e in events if e.get("type") == "done"), None)
    assert done is not None
    if not done.get("web_searched"):
        pytest.skip("web search not enabled/triggered on target (WEB_SEARCH_ENABLED off)")
    # if it ran, the answer should be non-empty
    text = "".join(e.get("content", "") for e in events if e.get("type") == "token")
    assert text.strip()


def test_transcribe_gate(client, user_headers):
    r = client.post(
        "/api/transcribe",
        headers=user_headers,
        files={"file": ("a.wav", b"RIFF....fake", "audio/wav")},
    )
    if r.status_code == 503:
        pytest.skip("VOICE_ENABLED off on target")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "text" in body or "transcript" in body


def test_webhook_roundtrip(client, user_headers):
    gen = client.post("/auth/me/webhook-token", headers=user_headers)
    assert gen.status_code in (200, 201), gen.text
    token = gen.json().get("webhook_token") or gen.json().get("token")
    assert token, gen.json()
    try:
        ev = client.post(
            f"/api/webhooks/{token}",
            json={"event_type": "reminder", "payload": {"note": f"verify-{uuid.uuid4().hex[:6]}"}},
        )
        assert ev.status_code in (200, 201, 202), ev.text
    finally:
        client.delete("/auth/me/webhook-token", headers=user_headers)


def test_vapid_key_and_push_subscribe(client, user_headers):
    key = client.get("/api/notifications/vapid-public-key", headers=user_headers)
    if key.status_code == 404:
        pytest.skip("web push not configured on target (VAPID keys unset)")
    assert key.status_code == 200
    sub = client.post(
        "/api/notifications/push/subscribe",
        headers=user_headers,
        json={"endpoint": "https://example.com/push/x", "keys": {"p256dh": "BdummyKey", "auth": "dummyAuth"}},
    )
    # accept success or validation error, but never a 500
    assert sub.status_code != 500, sub.text


def test_oauth_start_requires_google_creds(client, user_headers):
    r = client.get("/integrations/oauth/start", headers=user_headers, params={"connector_type": "google_drive"})
    if r.status_code in (404, 503):
        pytest.skip("INTEGRATION_SECRET / GOOGLE creds not configured on target")
    # when configured, it returns a consent URL (or redirects to one)
    assert r.status_code in (200, 302, 307), r.text
