import time
from typing import AsyncIterator

import httpx

from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, INTEGRATION_REDIRECT_BASE
from services.integrations.base import (
    AbstractConnector,
    ConnectorCredentials,
    OAuthTokens,
    SyncedChunk,
)
from services.integrations.registry import register

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"


@register
class GoogleDriveConnector(AbstractConnector):

    @classmethod
    def connector_type(cls) -> str:
        return "google_drive"

    @classmethod
    def get_auth_url(cls, state: str) -> str:
        redirect = f"{INTEGRATION_REDIRECT_BASE}/integrations/oauth/callback"
        return (
            f"{AUTH_URL}?response_type=code"
            f"&client_id={GOOGLE_CLIENT_ID}"
            f"&redirect_uri={redirect}"
            f"&scope={SCOPE}"
            f"&access_type=offline"
            f"&prompt=consent"
            f"&state={state}"
        )

    @classmethod
    async def exchange_code(cls, code: str) -> OAuthTokens:
        redirect = f"{INTEGRATION_REDIRECT_BASE}/integrations/oauth/callback"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=int(time.time()) + int(data.get("expires_in", 3600)),
            )

    @classmethod
    async def refresh_tokens(cls, credentials: ConnectorCredentials) -> ConnectorCredentials:
        if not credentials.get("refresh_token"):
            return credentials
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "refresh_token": credentials["refresh_token"],
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return ConnectorCredentials(
                access_token=data["access_token"],
                refresh_token=credentials["refresh_token"],
                expires_at=int(time.time()) + int(data.get("expires_in", 3600)),
            )

    async def iter_chunks(
        self, credentials: ConnectorCredentials, resource_id: str | None = None
    ) -> AsyncIterator[SyncedChunk]:
        return
        yield  # satisfies AsyncIterator type hint
