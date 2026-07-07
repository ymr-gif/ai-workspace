from abc import ABC, abstractmethod
from typing import AsyncIterator, TypedDict


class ReauthRequired(Exception):
    """Token refresh definitively rejected by the provider (e.g. Google
    invalid_grant: refresh token expired or revoked) — retrying cannot help,
    the user must reconnect the integration."""


class OAuthTokens(TypedDict, total=False):
    access_token: str
    refresh_token: str | None
    expires_at: int | None


class ConnectorCredentials(TypedDict):
    access_token: str
    refresh_token: str | None
    expires_at: int | None


class SyncedChunk(TypedDict):
    text: str
    filename: str
    mime_type: str


class AbstractConnector(ABC):

    @classmethod
    @abstractmethod
    def connector_type(cls) -> str: ...

    @classmethod
    @abstractmethod
    def get_auth_url(cls, state: str) -> str: ...

    @classmethod
    @abstractmethod
    async def exchange_code(cls, code: str) -> OAuthTokens: ...

    @classmethod
    @abstractmethod
    async def refresh_tokens(cls, credentials: ConnectorCredentials) -> ConnectorCredentials: ...

    @abstractmethod
    async def iter_chunks(
        self, credentials: ConnectorCredentials, resource_id: str | None = None
    ) -> AsyncIterator[SyncedChunk]: ...
