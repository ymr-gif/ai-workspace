import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AdminAuditLog, Conversation, Message, User


async def _audit(
    db:             AsyncSession,
    admin:          User,
    action:         str,
    target_user_id: int | None = None,
    detail:         dict | None = None,
) -> None:
    db.add(AdminAuditLog(
        id             = uuid.uuid4(),
        admin_id       = admin.id,
        action         = action,
        target_user_id = target_user_id,
        detail         = detail,
    ))


def _user_row(u, stats: dict) -> dict:
    return {
        "id":                u.id,
        "username":          u.username,
        "role":              u.role,
        "is_active":         u.is_active,
        "cost_limit_usd":    u.cost_limit_usd,
        "cost_window_days":  u.cost_window_days,
        "created_at":        u.created_at.isoformat(),
        "message_count":     stats.get("message_count", 0),
        "prompt_tokens":     stats.get("prompt_tokens",     0),
        "completion_tokens": stats.get("completion_tokens", 0),
        "total_tokens":      stats.get("total_tokens",      0),
        "cost_usd":          round(stats.get("cost_usd", 0.0) or 0.0, 6),
    }


async def _fetch_user_stats(db: AsyncSession, user_id: int | None = None) -> dict[int, dict]:
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


_SENSITIVE_SUFFIXES = ("KEY", "SECRET", "PASSWORD", "TOKEN")

def _mask(key: str, value: str | None) -> str | None:
    if value and any(key.upper().endswith(s) for s in _SENSITIVE_SUFFIXES):
        return value[:6] + "..."
    return value
