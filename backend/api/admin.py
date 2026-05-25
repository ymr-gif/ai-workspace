from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user, require_role
from core.db import get_db
from models import Conversation, Message, User

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_row(u, stats: dict) -> dict:
    return {
        "id":                u.id,
        "username":          u.username,
        "role":              u.role,
        "is_active":         u.is_active,
        "created_at":        u.created_at.isoformat(),
        "message_count":     stats.get("message_count", 0),
        "prompt_tokens":     stats.get("prompt_tokens",     0),
        "completion_tokens": stats.get("completion_tokens", 0),
        "total_tokens":      stats.get("total_tokens",      0),
        "cost_usd":          round(stats.get("cost_usd", 0.0) or 0.0, 6),
    }


async def _fetch_user_stats(db: AsyncSession, user_id: int | None = None) -> dict[int, dict]:
    """Return per-user aggregated token stats keyed by user_id."""
    q = (
        select(
            Conversation.user_id,
            func.count(Message.id).filter(Message.role == "assistant").label("message_count"),
            func.coalesce(func.sum(Message.prompt_tokens),     0).label("prompt_tokens"),
            func.coalesce(func.sum(Message.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(Message.total_tokens),      0).label("total_tokens"),
            func.coalesce(func.sum(Message.cost_usd),          0.0).label("cost_usd"),
        )
        .outerjoin(Message, (Message.conversation_id == Conversation.id) & (Message.role == "assistant"))
        .group_by(Conversation.user_id)
    )
    if user_id is not None:
        q = q.where(Conversation.user_id == user_id)

    rows = (await db.execute(q)).all()
    return {
        r.user_id: {
            "message_count":     r.message_count,
            "prompt_tokens":     r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens":      r.total_tokens,
            "cost_usd":          float(r.cost_usd or 0),
        }
        for r in rows
    }


@router.get("/users")
async def list_users(
    db:    AsyncSession = Depends(get_db),
    _:     User         = Depends(require_role("admin")),
):
    users  = (await db.execute(select(User).order_by(User.id))).scalars().all()
    stats  = await _fetch_user_stats(db)
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
    user_id:  int,
    db:       AsyncSession = Depends(get_db),
    admin:    User         = Depends(require_role("admin")),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    user.is_active = not user.is_active
    await db.commit()
    return {"id": user.id, "username": user.username, "is_active": user.is_active}
