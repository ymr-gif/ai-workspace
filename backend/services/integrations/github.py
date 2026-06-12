from typing import AsyncIterator

import httpx

from config import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, INTEGRATION_REDIRECT_BASE
from services.integrations.base import (
    AbstractConnector,
    ConnectorCredentials,
    OAuthTokens,
    SyncedChunk,
)
from services.integrations.registry import register

AUTH_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_BASE = "https://api.github.com"

TEXT_EXTENSIONS = frozenset({
    ".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".rst", ".html", ".css",
})
MAX_FILE_SIZE = 500 * 1024

BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".lib",
    ".mp3", ".mp4", ".avi", ".mov", ".webm", ".ogg", ".wav",
    ".db", ".sqlite", ".sqlite3", ".parquet", ".avro",
})


@register
class GitHubConnector(AbstractConnector):

    @classmethod
    def connector_type(cls) -> str:
        return "github"

    @classmethod
    def get_auth_url(cls, state: str) -> str:
        redirect = f"{INTEGRATION_REDIRECT_BASE}/integrations/oauth/callback"
        return (
            f"{AUTH_URL}?client_id={GITHUB_CLIENT_ID}"
            f"&redirect_uri={redirect}"
            f"&scope=repo"
            f"&state={state}"
        )

    @classmethod
    async def exchange_code(cls, code: str) -> OAuthTokens:
        redirect = f"{INTEGRATION_REDIRECT_BASE}/integrations/oauth/callback"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
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
            "Accept": "application/vnd.github.v3+json",
        }
        repo = resource_id or ""
        if not repo or "/" not in repo:
            return

        async with httpx.AsyncClient() as client:
            tree_url = f"{API_BASE}/repos/{repo}/git/trees/HEAD?recursive=1"
            resp = await client.get(tree_url, headers=headers)
            if resp.status_code != 200:
                return
            tree = resp.json()

            for item in tree.get("tree", []):
                if item["type"] != "blob":
                    continue
                path = item["path"]
                size = item.get("size", 0)

                if size > MAX_FILE_SIZE:
                    continue

                ext = _get_ext(path)
                if ext in BINARY_EXTENSIONS:
                    continue
                if ext not in TEXT_EXTENSIONS and not _looks_like_text(ext):
                    continue

                raw_url = item.get("url", "")
                raw_resp = await client.get(raw_url, headers={**headers, "Accept": "application/vnd.github.v3.raw"})
                if raw_resp.status_code != 200:
                    continue
                text = raw_resp.text

                yield SyncedChunk(
                    text=text,
                    filename=path.split("/")[-1],
                    mime_type="text/plain",
                )


def _get_ext(path: str) -> str:
    _, _, ext = path.rpartition(".")
    return f".{ext.lower()}" if ext else ""


def _looks_like_text(ext: str) -> bool:
    return ext in {"", ".cfg", ".conf", ".ini", ".env", ".gitignore", ".dockerignore",
                    ".editorconfig", ".prettierrc", ".eslintrc"}
