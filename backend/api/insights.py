import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import User, UserInsight

router = APIRouter(prefix="/insights", tags=["insights"])


def _row(i: UserInsight) -> dict:
    return {
        "id":         str(i.id),
        "content":    i.content,
        "is_read":    i.is_read,
        "created_at": i.created_at.isoformat(),
    }


@router.get("")
async def list_insights(
    all:          bool        = False,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    q = select(UserInsight).where(UserInsight.user_id == current_user.id)
    if not all:
        q = q.where(UserInsight.is_read == False)
    q = q.order_by(UserInsight.created_at.desc()).limit(50)
    result = await db.execute(q)
    return [_row(i) for i in result.scalars().all()]


@router.patch("/{insight_id}/read")
async def mark_read(
    insight_id:   str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        iid = uuid.UUID(insight_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid insight_id")
    row = await db.get(UserInsight, iid)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    row.is_read = True
    await db.commit()
    return _row(row)


@router.delete("/{insight_id}")
async def delete_insight(
    insight_id:   str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        iid = uuid.UUID(insight_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid insight_id")
    row = await db.get(UserInsight, iid)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
