from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from core.db import get_db
from models import ToolCallLog, User

router = APIRouter(prefix="/tool-calls", tags=["tools"])


@router.get("")
async def list_tool_calls(
    limit:           int         = Query(50, ge=1, le=200),
    conversation_id: str | None  = None,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    import uuid
    q = select(ToolCallLog).where(ToolCallLog.user_id == current_user.id)
    if conversation_id:
        try:
            cid = uuid.UUID(conversation_id)
            q = q.where(ToolCallLog.conversation_id == cid)
        except ValueError:
            pass
    q = q.order_by(ToolCallLog.created_at.desc()).limit(limit)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id":              str(log.id),
            "tool_name":       log.tool_name,
            "args":            log.args,
            "result_preview":  log.result_preview,
            "conversation_id": str(log.conversation_id) if log.conversation_id else None,
            "created_at":      log.created_at.isoformat(),
        }
        for log in logs
    ]
