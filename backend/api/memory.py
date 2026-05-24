from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from core.db import get_db
from models import User, UserMemory

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("")
async def get_memory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(UserMemory, current_user.id)
    if not row:
        return {"content": "", "project_summary": "", "version": 0, "updated_at": None}
    return {
        "content":         row.content         or "",
        "project_summary": row.project_summary or "",
        "version":         row.version,
        "updated_at":      row.updated_at.isoformat() if row.updated_at else None,
    }
