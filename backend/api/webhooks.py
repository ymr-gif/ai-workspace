import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.arq_pool import get_arq_pool
from core.db import get_db
from auth.security import get_current_user
from models import User, WebhookEvent

logger = logging.getLogger("api.webhooks")

VALID_EVENT_TYPES = frozenset({"file.uploaded", "reminder", "external.data"})


class WebhookPayload(BaseModel):
    event_type: str
    payload: dict


class WebhookTokenResponse(BaseModel):
    webhook_token: str | None


webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])
webhook_token_router = APIRouter(tags=["webhooks"])


@webhooks_router.post("/{user_token}", status_code=202)
async def receive_webhook(
    user_token: uuid.UUID,
    body: WebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    if body.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown event_type: {body.event_type}")

    result = await db.execute(
        select(User).where(User.webhook_token == user_token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid webhook token")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    event = WebhookEvent(
        user_id=user.id,
        event_type=body.event_type,
        payload=body.payload,
        status="pending",
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    pool = get_arq_pool()
    if pool:
        await pool.enqueue_job("process_webhook_job", event_id=str(event.id))
    else:
        import asyncio
        asyncio.create_task(_run_webhook_job_inline(str(event.id)))

    return {"queued": True, "event_id": str(event.id)}


async def _run_webhook_job_inline(event_id: str):
    try:
        from services.arq_worker import process_webhook_job
        await process_webhook_job({"job_try": 1}, event_id=event_id)
    except Exception as e:
        logger.error("[webhook] inline job failed event_id=%s err=%s", event_id, e)


@webhook_token_router.get("/webhook-token")
async def get_webhook_token(
    current_user: User = Depends(get_current_user),
):
    token = current_user.webhook_token
    return {"webhook_token": str(token) if token else None}


@webhook_token_router.post("/webhook-token")
async def generate_webhook_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = uuid.uuid4()
    current_user.webhook_token = token
    await db.commit()
    logger.info("[webhook] token generated user=%s", current_user.id)
    return {"webhook_token": str(token)}


@webhook_token_router.delete("/webhook-token", status_code=204)
async def revoke_webhook_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.webhook_token = None
    await db.commit()
    logger.info("[webhook] token revoked user=%s", current_user.id)
