import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from config import MODELS
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
            "system_prompt":  c.system_prompt  or "",
            "locked_model":   c.locked_model   or "",
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
    system_prompt:  str  | None = None   # "" clears
    locked_model:   str  | None = None   # "" or short key ("llama"…) or full model id; "" clears


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

    updated = body.model_dump(exclude_unset=True)

    if "memory_enabled" in updated:
        conv.memory_enabled = body.memory_enabled

    if "system_prompt" in updated:
        conv.system_prompt = body.system_prompt.strip() or None if body.system_prompt else None

    if "locked_model" in updated:
        raw = (body.locked_model or "").strip()
        if not raw:
            conv.locked_model = None
        else:
            # accept short key ("llama") or full model id
            conv.locked_model = MODELS.get(raw, raw) if raw in MODELS or raw in MODELS.values() else None

    await db.commit()
    return {
        "ok":             True,
        "memory_enabled": conv.memory_enabled,
        "system_prompt":  conv.system_prompt  or "",
        "locked_model":   conv.locked_model   or "",
    }


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
