from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user, require_role
from core.db import get_db
from models import AdminAuditLog, User

router = APIRouter()


@router.get("/audit-log")
async def get_audit_log(
    limit:          int       = Query(50, ge=1, le=200),
    offset:         int       = Query(0,  ge=0),
    action:         str | None = Query(None),
    target_user_id: int | None = Query(None),
    db:             AsyncSession = Depends(get_db),
    _:              User         = Depends(require_role("admin")),
):
    q = select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc())
    if action:
        q = q.where(AdminAuditLog.action == action)
    if target_user_id is not None:
        q = q.where(AdminAuditLog.target_user_id == target_user_id)
    q = q.offset(offset).limit(limit)

    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id":             str(r.id),
            "admin_id":       r.admin_id,
            "action":         r.action,
            "target_user_id": r.target_user_id,
            "detail":         r.detail,
            "created_at":     r.created_at.isoformat(),
        }
        for r in rows
    ]
