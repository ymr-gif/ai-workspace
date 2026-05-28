from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user, require_role
from core.db import get_db
from models import User

from .utils import _audit

router = APIRouter()


@router.post("/re-embed")
async def trigger_re_embed(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(require_role("admin")),
):
    from services.re_embed import queue_re_embed_force
    total = await queue_re_embed_force()
    await _audit(db, current_user, "re_embed.triggered", detail={"queued": total})
    await db.commit()
    return {"queued": total}
