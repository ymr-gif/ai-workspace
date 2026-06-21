"""Unit tests for Phase 3c Notifications — prefs CRUD, dispatch, rate limit, VAPID skip.

Run: pytest backend/tests/test_notifications.py -v
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY",  "test-key")
os.environ.setdefault("DATABASE_URL",    "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret")

import config
from api.notifications import router as notifications_router
from auth.security import get_current_user
from core.db import get_db
from models import User

fake_user = User(id=1, username="testuser", role="user", is_active=True)

async def _fake_user():
    return fake_user


def _make_client(db_mock):
    app = FastAPI()
    app.include_router(notifications_router, prefix="/api")
    app.dependency_overrides[get_current_user] = _fake_user

    async def _fake_get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _fake_get_db
    return TestClient(app)


# ── prefs CRUD ─────────────────────────────────────────────────────

def test_get_preferences_defaults():
    mock_db = AsyncMock(spec=object)
    mock_db.get = AsyncMock(return_value=None)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    client = _make_client(mock_db)
    resp = client.get("/api/notifications/preferences", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email_digest"] is True
    assert data["email_scheduled"] is True
    assert data["email_insights"] is True
    assert data["push_enabled"] is False


def test_patch_preferences():
    mock_prefs = MagicMock()
    mock_prefs.email_digest = True
    mock_prefs.email_scheduled = True
    mock_prefs.email_insights = True
    mock_prefs.push_enabled = False

    mock_db = AsyncMock(spec=object)
    mock_db.get = AsyncMock(return_value=mock_prefs)
    mock_db.commit = AsyncMock()

    client = _make_client(mock_db)
    resp = client.patch(
        "/api/notifications/preferences",
        json={"email_digest": False, "push_enabled": True},
        headers={"Authorization": "Bearer x"},
    )
    assert resp.status_code == 200
    assert mock_prefs.email_digest is False
    assert mock_prefs.push_enabled is True


# ── push subscribe ──────────────────────────────────────────────────

def test_push_subscribe():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_db = AsyncMock(spec=object)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    client = _make_client(mock_db)
    resp = client.post(
        "/api/notifications/push/subscribe",
        json={"endpoint": "https://push.example.com", "p256dh": "abc", "auth": "def"},
        headers={"Authorization": "Bearer x"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ── VAPID public key ────────────────────────────────────────────────

def test_vapid_public_key_not_configured():
    with patch("config.VAPID_PUBLIC_KEY", ""):
        mock_db = AsyncMock(spec=object)
        client = _make_client(mock_db)
        resp = client.get("/api/notifications/vapid-public-key", headers={"Authorization": "Bearer x"})
        assert resp.status_code == 404


def test_vapid_public_key_returns():
    with patch("config.VAPID_PUBLIC_KEY", "test-public-key"):
        mock_db = AsyncMock(spec=object)
        client = _make_client(mock_db)
        resp = client.get("/api/notifications/vapid-public-key", headers={"Authorization": "Bearer x"})
        assert resp.status_code == 200
        assert resp.json()["public_key"] == "test-public-key"


# ── notify dispatch ─────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("services.notification.get_redis")
@patch("services.notification.config.USE_REDIS", False)
async def test_notify_skips_when_no_smtp(mock_redis):
    from services.notification import notify

    config.SMTP_HOST = ""
    config.VAPID_PUBLIC_KEY = ""
    config.VAPID_PRIVATE_KEY = ""

    with patch("services.notification.AsyncSessionLocal") as mock_session:
        mock_db = AsyncMock(spec=object)
        mock_prefs = MagicMock()
        mock_prefs.email_digest = True
        mock_prefs.push_enabled = False

        mock_db.get = AsyncMock(return_value=mock_prefs)
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch("services.notification._send_email_notification", new_callable=AsyncMock) as mock_send:
            await notify(1, "digest", "Test", "Body")
            mock_send.assert_not_called()


@pytest.mark.asyncio
@patch("services.notification.get_redis")
@patch("services.notification.config.USE_REDIS", False)
@patch("services.notification.config.SMTP_HOST", "smtp.test.com")
async def test_notify_sends_email_when_configured(mock_redis):
    from services.notification import notify

    config.VAPID_PUBLIC_KEY = ""
    config.VAPID_PRIVATE_KEY = ""

    with patch("services.notification.AsyncSessionLocal") as mock_session:
        mock_db = AsyncMock(spec=object)
        mock_prefs = MagicMock()
        mock_prefs.email_digest = True
        mock_prefs.push_enabled = False

        mock_db.get = AsyncMock(return_value=mock_prefs)
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch("services.notification._send_email_notification", new_callable=AsyncMock) as mock_send:
            await notify(1, "digest", "Test", "Body")
            mock_send.assert_awaited_once()


@pytest.mark.asyncio
@patch("services.notification.get_redis")
@patch("services.notification.config.USE_REDIS", False)
async def test_notify_pref_off_skips_email(mock_redis):
    from services.notification import notify

    config.SMTP_HOST = "smtp.test.com"
    config.VAPID_PUBLIC_KEY = ""
    config.VAPID_PRIVATE_KEY = ""

    with patch("services.notification.AsyncSessionLocal") as mock_session:
        mock_db = AsyncMock(spec=object)
        mock_prefs = MagicMock()
        mock_prefs.email_digest = False
        mock_prefs.push_enabled = False

        mock_db.get = AsyncMock(return_value=mock_prefs)
        mock_session.return_value.__aenter__.return_value = mock_db

        with patch("services.notification._send_email_notification", new_callable=AsyncMock) as mock_send:
            await notify(1, "digest", "Test", "Body")
            mock_send.assert_not_called()
