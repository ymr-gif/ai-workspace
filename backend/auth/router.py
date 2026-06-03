import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import JWT_EXPIRE_MINUTES, REQUIRE_INVITE
from core.db import get_db
from auth.schemas import Token, RegisterRequest
from auth.security import authenticate_user, create_access_token, get_current_user, get_user, hash_password
from models import Invitation, User

logger      = logging.getLogger("auth")
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    expires = timedelta(minutes=JWT_EXPIRE_MINUTES)
    token   = create_access_token({"sub": user.username, "role": user.role}, expires_delta=expires)
    logger.info("[auth] login success username=%s", user.username)
    return Token(access_token=token, token_type="bearer", expires_in=int(expires.total_seconds()))


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=422, detail="username too short")
    if len(payload.password) < 6:
        raise HTTPException(status_code=422, detail="password too weak")

    if await get_user(username, db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    # Invite gate
    invite: Invitation | None = None
    if REQUIRE_INVITE:
        token = getattr(payload, "invite_token", None)
        if not token:
            raise HTTPException(status_code=403, detail="Invite token required")
        result = await db.execute(
            select(Invitation).where(Invitation.token == token).with_for_update()
        )
        invite = result.scalar_one_or_none()
        if not invite:
            raise HTTPException(status_code=403, detail="Invalid invite token")
        if invite.used_by_id is not None:
            raise HTTPException(status_code=403, detail="Invite token already used")
        if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="Invite token expired")

    user = User(username=username, hashed_password=hash_password(payload.password),
                role="user", is_active=True)
    try:
        db.add(user)
        await db.flush()

        # Mark invite as used
        if invite:
            invite.used_by_id = user.id
            invite.used_at    = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        logger.exception("[auth] register failed")
        raise HTTPException(status_code=500, detail="Registration failed")

    logger.info("[auth] registered username=%s", user.username)
    return {"username": user.username, "role": user.role}


@auth_router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role, "has_api_key": current_user.api_key is not None}


@auth_router.post("/me/api-key", status_code=201)
async def generate_api_key(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    key = secrets.token_urlsafe(48)
    current_user.api_key = key
    await db.commit()
    return {"api_key": key}


@auth_router.delete("/me/api-key")
async def revoke_api_key(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    current_user.api_key = None
    await db.commit()
    return {"ok": True}
