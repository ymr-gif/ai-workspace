import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from core.db import AsyncSessionLocal
from core.redis_client import get_redis
from models.notification import PushSubscription, UserNotificationPreferences

logger = logging.getLogger("services.notification")

_EVENT_TO_PREF = {
    "digest": "email_digest",
    "scheduled": "email_scheduled",
    "insight": "email_insights",
}


async def _load_prefs(user_id: int, db: AsyncSession) -> UserNotificationPreferences:
    row = await db.get(UserNotificationPreferences, user_id)
    if row is None:
        row = UserNotificationPreferences(
            user_id=user_id,
            email_digest=True,
            email_scheduled=True,
            email_insights=True,
            push_enabled=False,
        )
        db.add(row)
        await db.commit()
    return row


async def _check_rate_limit(user_id: int, event_type: str) -> bool:
    if not config.USE_REDIS:
        return True
    try:
        r = get_redis()
        key = f"notif:rl:{user_id}:{event_type}"
        current = await r.incr(key)
        if current == 1:
            await r.expire(key, config.NOTIFICATION_RATE_WINDOW)
        if current > config.NOTIFICATION_RATE_LIMIT:
            logger.warning("[notif] rate limited user=%s event=%s", user_id, event_type)
            return False
    except Exception as e:
        logger.warning("[notif] rate limit check failed: %s", e)
    return True


async def notify(user_id: int, event_type: str, subject: str, body: str, url: str | None = None) -> None:
    if not await _check_rate_limit(user_id, event_type):
        return

    async with AsyncSessionLocal() as db:
        prefs = await _load_prefs(user_id, db)
        email_field = _EVENT_TO_PREF.get(event_type)
        send_email_ch = email_field and getattr(prefs, email_field, False) and config.SMTP_HOST
        send_push_ch = prefs.push_enabled and config.VAPID_PUBLIC_KEY and config.VAPID_PRIVATE_KEY

    if send_email_ch:
        await _send_email_notification(user_id, subject, body)

    if send_push_ch:
        await _send_push_notification(user_id, subject, body, url)


async def _send_email_notification(user_id: int, subject: str, body: str) -> None:
    from services.email import send_email

    async with AsyncSessionLocal() as db:
        from models import User
        user = await db.get(User, user_id)
        if not user or not user.email:
            return
        try:
            await send_email(to=user.email, subject=subject, body=body)
        except Exception as e:
            logger.warning("[notif] email failed user=%s err=%s", user_id, e)


async def _send_push_notification(user_id: int, subject: str, body: str, url: str | None = None) -> None:
    from pywebpush import webpush, WebPushException

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        subs = result.scalars().all()

    payload = json.dumps({
        "title": subject,
        "body": body,
        "url": url or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=config.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": config.VAPID_SUBJECT},
            )
        except WebPushException as e:
            if e.response and e.response.status_code in (410, 404):
                async with AsyncSessionLocal() as db:
                    await db.delete(sub)
                    await db.commit()
                logger.info("[notif] removed expired push sub user=%s", user_id)
            else:
                logger.warning("[notif] push failed user=%s err=%s", user_id, e)
        except Exception as e:
            logger.warning("[notif] push failed user=%s err=%s", user_id, e)
