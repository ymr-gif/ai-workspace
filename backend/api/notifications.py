import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from auth.security import get_current_user
from core.db import get_db
from models import PushSubscription, User, UserNotificationPreferences

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger("api.notifications")


class PrefsUpdate(BaseModel):
    email_digest: bool | None = None
    email_scheduled: bool | None = None
    email_insights: bool | None = None
    push_enabled: bool | None = None


class PushSubscribeBody(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


@router.get("/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await db.get(UserNotificationPreferences, current_user.id)
    if prefs is None:
        prefs = UserNotificationPreferences(
            user_id=current_user.id,
            email_digest=True,
            email_scheduled=True,
            email_insights=True,
            push_enabled=False,
        )
        db.add(prefs)
        await db.commit()
    return {
        "email_digest": prefs.email_digest,
        "email_scheduled": prefs.email_scheduled,
        "email_insights": prefs.email_insights,
        "push_enabled": prefs.push_enabled,
    }


@router.patch("/preferences")
async def update_preferences(
    body: PrefsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await db.get(UserNotificationPreferences, current_user.id)
    if prefs is None:
        prefs = UserNotificationPreferences(
            user_id=current_user.id,
            email_digest=True,
            email_scheduled=True,
            email_insights=True,
            push_enabled=False,
        )
        db.add(prefs)
        await db.flush()

    if body.email_digest is not None:
        prefs.email_digest = body.email_digest
    if body.email_scheduled is not None:
        prefs.email_scheduled = body.email_scheduled
    if body.email_insights is not None:
        prefs.email_insights = body.email_insights
    if body.push_enabled is not None:
        prefs.push_enabled = body.push_enabled
    await db.commit()
    return {"ok": True}


@router.post("/push/subscribe")
async def subscribe_push(
    body: PushSubscribeBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == body.endpoint,
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True, "already_subscribed": True}

    sub = PushSubscription(
        user_id=current_user.id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
    )
    db.add(sub)
    await db.commit()
    return {"ok": True}


@router.get("/vapid-public-key")
async def vapid_public_key():
    if not config.VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=404, detail="VAPID not configured")
    return {"public_key": config.VAPID_PUBLIC_KEY}
