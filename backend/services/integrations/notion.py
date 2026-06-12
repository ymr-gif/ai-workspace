from typing import AsyncIterator
import base64

import httpx

from config import NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, INTEGRATION_REDIRECT_BASE
from services.integrations.base import (
    AbstractConnector,
    ConnectorCredentials,
    OAuthTokens,
    SyncedChunk,
)
from services.integrations.registry import register

AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_VERSION = "2022-06-28"


@register
class NotionConnector(AbstractConnector):

    @classmethod
    def connector_type(cls) -> str:
        return "notion"

    @classmethod
    def get_auth_url(cls, state: str) -> str:
        redirect = f"{INTEGRATION_REDIRECT_BASE}/api/integrations/oauth/callback"
        return (
            f"{AUTH_URL}?client_id={NOTION_CLIENT_ID}"
            f"&redirect_uri={redirect}"
            f"&response_type=code"
            f"&state={state}"
        )

    @classmethod
    async def exchange_code(cls, code: str) -> OAuthTokens:
        redirect = f"{INTEGRATION_REDIRECT_BASE}/api/integrations/oauth/callback"
        basic = base64.b64encode(
            f"{NOTION_CLIENT_ID}:{NOTION_CLIENT_SECRET}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/json",
                },
                json={
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return OAuthTokens(
                access_token=data["access_token"],
                refresh_token=None,
                expires_at=None,
            )

    @classmethod
    async def refresh_tokens(cls, credentials: ConnectorCredentials) -> ConnectorCredentials:
        return credentials

    async def iter_chunks(
        self, credentials: ConnectorCredentials, resource_id: str | None = None
    ) -> AsyncIterator[SyncedChunk]:
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Notion-Version": NOTION_VERSION,
        }
        db_id = resource_id

        async with httpx.AsyncClient() as client:
            cursor = None
            while True:
                body: dict = {"page_size": 100}
                if cursor:
                    body["start_cursor"] = cursor

                resp = await client.post(
                    f"https://api.notion.com/v1/databases/{db_id}/query",
                    headers=headers,
                    json=body,
                )
                if resp.status_code == 404:
                    return
                resp.raise_for_status()
                data = resp.json()

                for page in data.get("results", []):
                    page_id = page["id"]
                    title = _extract_page_title(page)
                    text = await _fetch_page_text(page_id, headers)
                    yield SyncedChunk(
                        text=text,
                        filename=f"{title or page_id}.md",
                        mime_type="text/markdown",
                    )

                cursor = data.get("next_cursor")
                if not cursor:
                    break


async def _fetch_page_text(page_id: str, headers: dict) -> str:
    parts: list[str] = []
    async with httpx.AsyncClient() as client:
        cursor = None
        while True:
            url = f"https://api.notion.com/v1/blocks/{page_id}/children"
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor

            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                break
            data = resp.json()

            for block in data.get("results", []):
                text = _block_to_text(block)
                if text:
                    parts.append(text)

            cursor = data.get("next_cursor")
            if not cursor:
                break

    return "\n\n".join(parts)


def _extract_page_title(page: dict) -> str:
    try:
        props = page.get("properties", {})
        for prop in props.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_parts)
    except Exception:
        pass
    return ""


def _block_to_text(block: dict) -> str:
    block_type = block.get("type", "")
    inner = block.get(block_type, {})
    rich_text = inner.get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in rich_text)
