import json
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from config import MODELS
from core.db import get_db
from models import Conversation, Message, User

logger = logging.getLogger("conversations")
router = APIRouter()


@router.get("/conversations")
async def list_conversations(
    q:            str | None   = None,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(100)
    )

    if q and q.strip():
        stmt = (
            stmt
            .join(Message, Message.conversation_id == Conversation.id)
            .where(text("messages.content_tsv @@ websearch_to_tsquery('simple', :q)").bindparams(q=q.strip()))
            .distinct()
        )

    result = await db.execute(stmt)
    convs  = result.scalars().all()
    return [
        {
            "id":             str(c.id),
            "title":          c.title,
            "updated_at":     c.updated_at.isoformat(),
            "memory_enabled": True,
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
        {
            "role":              m.role,
            "content":           m.content,
            "model":             m.model,
            "prompt_tokens":     m.prompt_tokens,
            "completion_tokens": m.completion_tokens,
            "total_tokens":      m.total_tokens,
            "cost_usd":          m.cost_usd,
            "activity_trace":    m.activity_trace,
        }
        for m in msgs
    ]


def _safe_filename(title: str, ext: str) -> str:
    safe = re.sub(r'[\"\r\n\x00-\x1f\\]', '', title)[:40].strip() or 'conversation'
    return f"{safe}.{ext}"


class ConversationPatch(BaseModel):
    system_prompt: str | None = None
    locked_model:  str | None = None


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

    if "system_prompt" in updated:
        conv.system_prompt = body.system_prompt.strip() or None if body.system_prompt else None

    if "locked_model" in updated:
        raw = (body.locked_model or "").strip()
        if not raw:
            conv.locked_model = None
        else:
            conv.locked_model = MODELS.get(raw, raw) if raw in MODELS or raw in MODELS.values() else None

    await db.commit()
    return {
        "ok":             True,
        "memory_enabled": True,
        "system_prompt":  conv.system_prompt  or "",
        "locked_model":   conv.locked_model   or "",
    }


@router.get("/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: str,
    format:          str          = "markdown",
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

    if format == "json":
        payload = json.dumps([
            {
                "role":              m.role,
                "content":           m.content,
                "model":             m.model,
                "created_at":        m.created_at.isoformat(),
                "prompt_tokens":     m.prompt_tokens,
                "completion_tokens": m.completion_tokens,
                "total_tokens":      m.total_tokens,
                "cost_usd":          m.cost_usd,
            }
            for m in msgs
        ], indent=2)
        return StreamingResponse(
            iter([payload]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=\"{_safe_filename(conv.title, 'json')}\""},
        )

    def _md_lines():
        yield f"# {conv.title}\n\n"
        for m in msgs:
            label = "**User:**" if m.role == "user" else f"**AI** ({m.model or 'unknown'}):"
            yield f"{label}\n\n{m.content}\n\n---\n\n"

    return StreamingResponse(
        _md_lines(),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=\"{_safe_filename(conv.title, 'md')}\""},
    )


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
