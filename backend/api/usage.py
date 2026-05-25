from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import Conversation, Message, User

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def get_my_usage(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    """Current user's aggregate token usage and estimated cost."""
    row = (await db.execute(
        select(
            func.count(Message.id).filter(Message.role == "assistant").label("message_count"),
            func.coalesce(func.sum(Message.prompt_tokens),     0).label("prompt_tokens"),
            func.coalesce(func.sum(Message.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(Message.total_tokens),      0).label("total_tokens"),
            func.coalesce(func.sum(Message.cost_usd),          0.0).label("cost_usd"),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == current_user.id, Message.role == "assistant")
    )).one()

    return {
        "username":          current_user.username,
        "message_count":     row.message_count,
        "prompt_tokens":     row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "total_tokens":      row.total_tokens,
        "cost_usd":          round(float(row.cost_usd or 0), 6),
    }


@router.get("/history")
async def get_my_usage_history(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    """Per-conversation token usage breakdown for current user."""
    convs = (await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
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
            "created_at":        conv.created_at.isoformat(),
            "message_count":     row.msgs,
            "prompt_tokens":     row.pt,
            "completion_tokens": row.ct,
            "total_tokens":      row.tt,
            "cost_usd":          round(float(row.cost or 0), 6),
        })

    return {"conversations": breakdown}
