"""Google OAuth refresh — invalid_grant → ReauthRequired mapping. Mocked httpx, no live Google."""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from services.integrations.base import ReauthRequired
from services.integrations.google_oauth import GoogleOAuthConnector

CREDS = {"access_token": "old", "refresh_token": "rt", "expires_at": 0}


def _patched_client(resp):
    client = AsyncMock()
    client.post.return_value = resp
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch("services.integrations.google_oauth.httpx.AsyncClient", return_value=cm)


@pytest.mark.asyncio
async def test_invalid_grant_raises_reauth_required():
    resp = MagicMock(status_code=400, text='{"error": "invalid_grant", "error_description": "Token has been expired or revoked."}')
    with _patched_client(resp):
        with pytest.raises(ReauthRequired):
            await GoogleOAuthConnector.refresh_tokens(dict(CREDS))


@pytest.mark.asyncio
async def test_other_400_still_raises_http_error():
    resp = MagicMock(status_code=400, text='{"error": "invalid_client"}')
    resp.raise_for_status.side_effect = httpx.HTTPStatusError("400", request=MagicMock(), response=resp)
    with _patched_client(resp):
        with pytest.raises(httpx.HTTPStatusError):
            await GoogleOAuthConnector.refresh_tokens(dict(CREDS))


@pytest.mark.asyncio
async def test_successful_refresh_keeps_refresh_token():
    resp = MagicMock(status_code=200, text="{}")
    resp.json.return_value = {"access_token": "new", "expires_in": 3600}
    with _patched_client(resp):
        out = await GoogleOAuthConnector.refresh_tokens(dict(CREDS))
    assert out["access_token"] == "new"
    assert out["refresh_token"] == "rt"


@pytest.mark.asyncio
async def test_no_refresh_token_returns_credentials_unchanged():
    creds = {"access_token": "old", "refresh_token": None, "expires_at": 0}
    out = await GoogleOAuthConnector.refresh_tokens(creds)
    assert out is creds
