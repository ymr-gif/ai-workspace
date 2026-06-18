from typing import AsyncIterator

from services.integrations.base import ConnectorCredentials, SyncedChunk
from services.integrations.google_oauth import GoogleOAuthConnector
from services.integrations.registry import register


@register
class GoogleCalendarConnector(GoogleOAuthConnector):

    SCOPE = "https://www.googleapis.com/auth/calendar.events"

    @classmethod
    def connector_type(cls) -> str:
        return "google_calendar"

    async def iter_chunks(
        self, credentials: ConnectorCredentials, resource_id: str | None = None
    ) -> AsyncIterator[SyncedChunk]:
        return
        yield
