import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import User, UserGoal

router = APIRouter(prefix="/goals", tags=["goals"])
logger = logging.getLogger("goals")


def _row(g: UserGoal) -> dict:
    return {
        "id":                      str(g.id),
        "title":                   g.title,
        "description":             g.description,
        "status":                  g.status,
        "linked_conversation_ids": g.linked_conversation_ids or [],
        "created_at":              g.created_at.isoformat(),
        "updated_at":              g.updated_at.isoformat(),
    }


class GoalCreate(BaseModel):
    title:       str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    status:      str | None = Field(None, pattern=r"^(active|completed|paused)$")


class GoalPatch(BaseModel):
    title:       str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status:      str | None = Field(None, pattern=r"^(active|completed|paused)$")


@router.get("")
async def list_goals(
    status:       str | None = None,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    stmt = select(UserGoal).where(UserGoal.user_id == current_user.id)
    if status:
        stmt = stmt.where(UserGoal.status == status)
    stmt = stmt.order_by(UserGoal.created_at.desc())
    result = await db.execute(stmt)
    return [_row(g) for g in result.scalars().all()]


@router.post("", status_code=201)
async def create_goal(
    body:         GoalCreate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    g = UserGoal(
        user_id     = current_user.id,
        title       = body.title.strip(),
        description = body.description.strip() if body.description else None,
        status      = body.status or "active",
    )
    db.add(g)
    await db.commit()
    return _row(g)


@router.patch("/{goal_id}")
async def patch_goal(
    goal_id:      str,
    body:         GoalPatch,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        gid = uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    g = await db.get(UserGoal, gid)
    if not g or g.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    updated = body.model_dump(exclude_unset=True)
    if "title"       in updated: g.title       = body.title.strip()
    if "description" in updated: g.description = body.description.strip() if body.description else None
    if "status"      in updated: g.status      = body.status

    await db.commit()
    return _row(g)


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id:      str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        gid = uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    g = await db.get(UserGoal, gid)
    if not g or g.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    await db.delete(g)
    await db.commit()


@router.post("/{goal_id}/link/{conversation_id}")
async def link_conversation(
    goal_id:         str,
    conversation_id: str,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    try:
        gid = uuid.UUID(goal_id)
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    g = await db.get(UserGoal, gid)
    if not g or g.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    ids = g.linked_conversation_ids or []
    sid = str(cid)
    if sid not in ids:
        ids.append(sid)
        g.linked_conversation_ids = ids
        await db.commit()

    return _row(g)
