from typing import AsyncIterator

from services.integrations.base import ConnectorCredentials, SyncedChunk
from services.integrations.google_oauth import GoogleOAuthConnector
from services.integrations.registry import register

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@register
class GmailConnector(GoogleOAuthConnector):

    SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

    @classmethod
    def connector_type(cls) -> str:
        return "gmail"

    async def iter_chunks(
        self, credentials: ConnectorCredentials, resource_id: str | None = None
    ) -> AsyncIterator[SyncedChunk]:
        return
        yield
