import asyncio
import json as _json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import User

from .utils import _get_file_or_404

router = APIRouter()


@router.get("/{file_id}/status/stream")
async def stream_file_status(
    file_id:      str,
    request:      Request,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    fid, f = await _get_file_or_404(file_id, db, current_user.id)

    async def status_events():
        last_status = None
        last_pct    = None
        pkey        = f"proc_progress:{fid}"
        redis = None
        try:
            from core.redis_client import get_redis
            redis = get_redis()
        except Exception:
            pass

        try:
            while True:
                db.expire(f)
                await db.refresh(f)
                status = f.upload_status

                pct = None
                if status == "processing" and redis:
                    try:
                        val = await redis.get(pkey)
                        pct = float(val) if val else None
                    except Exception:
                        redis = None

                if status != last_status or pct != last_pct:
                    last_status = status
                    last_pct    = pct
                    data = {"id": str(fid), "status": status}
                    if pct is not None:
                        data["progress"] = pct
                    yield f"data: {_json.dumps(data)}\n\n"

                if status in ("ready", "error"):
                    break
                await asyncio.sleep(0.8)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        status_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
