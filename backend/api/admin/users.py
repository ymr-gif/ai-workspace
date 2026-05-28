from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user, require_role
from core.db import get_db
from models import Conversation, Message, User

from .utils import _audit, _user_row, _fetch_user_stats

router = APIRouter()


class CostLimitRequest(BaseModel):
    cost_limit_usd:   float | None = None
    cost_window_days: int | None  = 30


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(require_role("admin")),
):
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    stats = await _fetch_user_stats(db)
    return [_user_row(u, stats.get(u.id, {})) for u in users]


@router.get("/users/{user_id}/usage")
async def get_user_usage(
    user_id: int,
    db:      AsyncSession = Depends(get_db),
    _:       User         = Depends(require_role("admin")),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    convs = (await db.execute(
        select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.created_at.desc())
    )).scalars().all()

    breakdown = []
    for conv in convs:
        row = (await db.execute(
            select(
                func.count(Message.id).filter(Message.role == "assistant").label("msgs"),
                func.coalesce(func.sum(Message.prompt_tokens),     0).label("pt"),
                func.coalesce(func.sum(Message.completion_tokens), 0).label("ct"),
                func.coalesce(func.sum(Message.total_tokens),      0).label("tt"),
                func.coalesce(func.sum(Message.cost_usd),          0.0).label("cost"),
            )
            .where(Message.conversation_id == conv.id, Message.role == "assistant")
        )).one()
        breakdown.append({
            "conversation_id":   str(conv.id),
            "title":             conv.title,
            "message_count":     row.msgs,
            "prompt_tokens":     row.pt,
            "completion_tokens": row.ct,
            "total_tokens":      row.tt,
            "cost_usd":          round(float(row.cost or 0), 6),
        })

    stats = await _fetch_user_stats(db, user_id=user_id)
    return {
        "user":      _user_row(user, stats.get(user_id, {})),
        "breakdown": breakdown,
    }


@router.patch("/users/{user_id}/active")
async def toggle_user_active(
    user_id: int,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(require_role("admin")),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    user.is_active = not user.is_active
    action = "user.active.enabled" if user.is_active else "user.active.disabled"
    await _audit(db, admin, action, target_user_id=user_id,
                 detail={"username": user.username, "is_active": user.is_active})
    await db.commit()
    return {"id": user.id, "username": user.username, "is_active": user.is_active}


@router.patch("/users/{user_id}/cost-limit")
async def set_cost_limit(
    user_id: int,
    body:    CostLimitRequest,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(require_role("admin")),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.cost_limit_usd is not None and body.cost_limit_usd < 0:
        raise HTTPException(status_code=400, detail="cost_limit_usd must be >= 0")
    if body.cost_window_days is not None and body.cost_window_days < 1:
        raise HTTPException(status_code=400, detail="cost_window_days must be >= 1")

    prev_limit  = user.cost_limit_usd
    prev_window = user.cost_window_days
    user.cost_limit_usd  = body.cost_limit_usd
    user.cost_window_days = body.cost_window_days if body.cost_limit_usd is not None else None

    action = "user.cost_limit.removed" if body.cost_limit_usd is None else "user.cost_limit.set"
    await _audit(db, admin, action, target_user_id=user_id, detail={
        "username":          user.username,
        "prev_limit_usd":    prev_limit,
        "new_limit_usd":     user.cost_limit_usd,
        "prev_window_days":  prev_window,
        "new_window_days":   user.cost_window_days,
    })
    await db.commit()
    return {
        "id":               user.id,
        "username":         user.username,
        "cost_limit_usd":   user.cost_limit_usd,
        "cost_window_days": user.cost_window_days,
    }
