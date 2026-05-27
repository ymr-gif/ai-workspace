import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user, require_role
from core.db import get_db
from models import User

logger        = logging.getLogger("auth.invites")
invite_router = APIRouter(prefix="/auth", tags=["auth"])


@invite_router.post("/invite", status_code=201)
async def create_invite(
    email:        str | None = None,
    current_user: User       = Depends(require_role("admin")),
    db:           AsyncSession = Depends(get_db),
):
    """Admin: generate an invite token. Invite model added in migration 021."""
    from models import Invitation
    from datetime import datetime, timezone, timedelta

    token      = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    invite     = Invitation(
        token          = token,
        created_by_id  = current_user.id,
        email          = email,
        expires_at     = expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    logger.info("[invite] created by=%s token=%s...", current_user.username, token[:8])
    return {"token": token, "expires_at": expires_at.isoformat(), "email": email}


@invite_router.get("/invites")
async def list_invites(
    current_user: User         = Depends(require_role("admin")),
    db:           AsyncSession = Depends(get_db),
):
    """Admin: list all invitations."""
    from sqlalchemy import select
    from models import Invitation

    result = await db.execute(
        select(Invitation).order_by(Invitation.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "id":           str(r.id),
            "token_prefix": r.token[:8] + "...",
            "email":        r.email,
            "used":         r.used_by_id is not None,
            "expires_at":   r.expires_at.isoformat() if r.expires_at else None,
            "created_at":   r.created_at.isoformat(),
        }
        for r in rows
    ]
