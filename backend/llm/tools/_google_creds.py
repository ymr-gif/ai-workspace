import time
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.encryption import decrypt_token, encrypt_token
from models import ExternalSource
from services.integrations.base import AbstractConnector

logger = logging.getLogger("tools.google_creds")


async def load_google_credentials(
    db: AsyncSession,
    user_id: int,
    connector_type: str,
    connector_cls: type[AbstractConnector],
) -> tuple[ExternalSource | None, dict | None]:
    src = await db.scalar(
        select(ExternalSource).where(
            ExternalSource.user_id == user_id,
            ExternalSource.connector_type == connector_type,
            ExternalSource.status == "active",
        )
    )
    if not src or not src.credentials:
        return None, None

    creds = {
        "access_token": decrypt_token(src.credentials["access_token"]),
        "refresh_token": decrypt_token(src.credentials["refresh_token"]) if src.credentials.get("refresh_token") else None,
        "expires_at": src.credentials.get("expires_at"),
    }

    if creds.get("expires_at") and creds["expires_at"] < int(time.time()):
        if not creds.get("refresh_token"):
            src.status = "needs_reauth"
            await db.commit()
            return src, None
        creds = await connector_cls.refresh_tokens(creds)
        src.credentials = {
            "access_token": encrypt_token(creds["access_token"]),
            "expires_at": creds.get("expires_at"),
        }
        if creds.get("refresh_token"):
            src.credentials["refresh_token"] = encrypt_token(creds["refresh_token"])
        await db.commit()

    return src, creds
