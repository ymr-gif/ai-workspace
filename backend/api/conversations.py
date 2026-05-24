import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import Conversation, Message, User

logger = logging.getLogger("conversations")
router = APIRouter()


@router.get("/conversations")
async def list_conversations(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [
        {
            "id":             str(c.id),
            "title":          c.title,
            "updated_at":     c.updated_at.isoformat(),
            "memory_enabled": c.memory_enabled,
        }
        for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    conv = await db.get(Conversation, cid)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == cid)
        .order_by(Message.created_at.asc())
    )
    msgs = result.scalars().all()
    return [
        {"role": m.role, "content": m.content, "model": m.model}
        for m in msgs
    ]


class ConversationPatch(BaseModel):
    memory_enabled: bool | None = None


@router.patch("/conversations/{conversation_id}")
async def patch_conversation(
    conversation_id: str,
    body:            ConversationPatch,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    conv = await db.get(Conversation, cid)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    if body.memory_enabled is not None:
        conv.memory_enabled = body.memory_enabled

    await db.commit()
    return {"ok": True, "memory_enabled": conv.memory_enabled}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    conv = await db.get(Conversation, cid)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    await db.delete(conv)
    await db.commit()
    return {"ok": True}
