import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import Conversation, PromptTemplate, User

router = APIRouter(prefix="/templates", tags=["templates"])


def _row(t: PromptTemplate, user_id: int) -> dict:
    return {
        "id":          str(t.id),
        "user_id":     t.user_id,
        "name":        t.name,
        "description": t.description or "",
        "content":     t.content,
        "is_shared":   t.is_shared,
        "is_owner":    t.user_id == user_id,
        "created_at":  t.created_at.isoformat(),
        "updated_at":  t.updated_at.isoformat(),
    }


class TemplateCreate(BaseModel):
    name:        str  = Field(..., min_length=1, max_length=100)
    description: str | None = None
    content:     str  = Field(..., min_length=1)
    is_shared:   bool = False


class TemplateUpdate(BaseModel):
    name:        str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    content:     str | None = Field(None, min_length=1)
    is_shared:   bool | None = None


@router.post("", status_code=201)
async def create_template(
    body:         TemplateCreate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    t = PromptTemplate(
        user_id     = current_user.id,
        name        = body.name.strip(),
        description = body.description,
        content     = body.content,
        is_shared   = body.is_shared,
    )
    db.add(t)
    await db.commit()
    return _row(t, current_user.id)


@router.get("")
async def list_templates(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(PromptTemplate)
        .where(or_(PromptTemplate.user_id == current_user.id, PromptTemplate.is_shared == True))
        .order_by(PromptTemplate.updated_at.desc())
    )
    return [_row(t, current_user.id) for t in result.scalars().all()]


@router.get("/{template_id}")
async def get_template(
    template_id:  str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    t = await db.get(PromptTemplate, tid)
    if not t or (t.user_id != current_user.id and not t.is_shared):
        raise HTTPException(status_code=404, detail="Not found")
    return _row(t, current_user.id)


@router.put("/{template_id}")
async def update_template(
    template_id:  str,
    body:         TemplateUpdate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    t = await db.get(PromptTemplate, tid)
    if not t or t.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not owner")

    updated = body.model_dump(exclude_unset=True)
    if "name"        in updated: t.name        = body.name.strip()
    if "description" in updated: t.description = body.description
    if "content"     in updated: t.content     = body.content
    if "is_shared"   in updated: t.is_shared   = body.is_shared
    t.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _row(t, current_user.id)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id:  str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    t = await db.get(PromptTemplate, tid)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    if t.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not owner")

    await db.delete(t)
    await db.commit()


@router.post("/{template_id}/apply/{conversation_id}")
async def apply_template(
    template_id:     str,
    conversation_id: str,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    try:
        tid = uuid.UUID(template_id)
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")

    t = await db.get(PromptTemplate, tid)
    if not t or (t.user_id != current_user.id and not t.is_shared):
        raise HTTPException(status_code=404, detail="Template not found")

    conv = await db.get(Conversation, cid)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.system_prompt = t.content
    await db.commit()
    return {"ok": True, "conversation_id": str(cid), "template_id": str(tid)}
