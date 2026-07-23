import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import config
from config import GITHUB_CLIENT_ID, GOOGLE_CLIENT_ID, NOTION_CLIENT_ID
from core.arq_pool import get_arq_pool
from core.db import get_db
from core.encryption import decrypt_token, encrypt_token, fernet_ready
from core.redis_client import get_redis
from auth.security import get_current_user
from models import ExternalSource, User
from services.integrations.registry import get_connector

_CLIENT_ID_MAP: dict[str, tuple[str, str]] = {
    "google_drive":     (GOOGLE_CLIENT_ID, "GOOGLE_CLIENT_ID"),
    "google_calendar":  (GOOGLE_CLIENT_ID, "GOOGLE_CLIENT_ID"),
    "gmail":            (GOOGLE_CLIENT_ID, "GOOGLE_CLIENT_ID"),
    "notion":           (NOTION_CLIENT_ID, "NOTION_CLIENT_ID"),
    "github":           (GITHUB_CLIENT_ID, "GITHUB_CLIENT_ID"),
}

logger = logging.getLogger("api.integrations")

_VALID_TYPES = frozenset({"google_drive", "google_calendar", "gmail", "notion", "github"})

STATE_TTL = 600

# ── Schemas ────────────────────────────────────────────────────────────────────


class SourceCreate(BaseModel):
    connector_type: str = Field(pattern=r"^(google_drive|google_calendar|gmail|notion|github)$")
    display_name: str | None = None
    resource_id: str | None = None


class SourcePatch(BaseModel):
    display_name: str | None = None
    resource_id: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|paused)$")


class SourceRow(BaseModel):
    id: str
    connector_type: str
    display_name: str | None
    resource_id: str | None
    status: str
    error: str | None
    last_sync_at: str | None
    created_at: str

    model_config = {"from_attributes": True}


# ── Helpers ────────────────────────────────────────────────────────────────────


def _row(src: ExternalSource) -> SourceRow:
    return SourceRow(
        id=str(src.id),
        connector_type=src.connector_type,
        display_name=src.display_name,
        resource_id=src.resource_id,
        status=src.status,
        error=src.error,
        last_sync_at=src.last_sync_at.isoformat() if src.last_sync_at else None,
        created_at=src.created_at.isoformat() if src.created_at else None,
    )


# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ── CRUD endpoints ─────────────────────────────────────────────────────────────


@router.get("/available")
async def available_connector_types(
    current_user: User = Depends(get_current_user),
):
    """Which connector_type values the UI should offer an OAuth button for (QUEUE
    Q0.6). Read as config.ENABLED_CONNECTOR_TYPES at request time (not imported at
    module load) so POST /admin/env/reload flips this with no frontend rebuild — a
    Vite import.meta.env var would be inlined at build time and could not. Empty
    list (default) = every connector stays stubbed."""
    return {"types": list(config.ENABLED_CONNECTOR_TYPES)}


@router.get("", response_model=list[SourceRow])
async def list_sources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExternalSource)
        .where(ExternalSource.user_id == current_user.id)
        .order_by(ExternalSource.created_at.desc())
    )
    return [_row(s) for s in result.scalars().all()]


@router.post("", response_model=SourceRow, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not fernet_ready():
        raise HTTPException(status_code=503, detail="Encryption not configured (INTEGRATION_SECRET missing)")

    src = ExternalSource(
        user_id=current_user.id,
        connector_type=body.connector_type,
        display_name=body.display_name,
        resource_id=body.resource_id,
    )
    db.add(src)
    try:
        await db.commit()
        await db.refresh(src)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Source already exists for this user/type/resource")
    return _row(src)


@router.get("/{source_id}", response_model=SourceRow)
async def get_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = await db.get(ExternalSource, source_id)
    if not src or src.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Source not found")
    return _row(src)


@router.patch("/{source_id}", response_model=SourceRow)
async def patch_source(
    source_id: uuid.UUID,
    body: SourcePatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = await db.get(ExternalSource, source_id)
    if not src or src.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(src, key, value)
    await db.commit()
    await db.refresh(src)
    return _row(src)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = await db.get(ExternalSource, source_id)
    if not src or src.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(src)
    await db.commit()


# ── Sync endpoint ──────────────────────────────────────────────────────────────


@router.post("/{source_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_source(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = await db.get(ExternalSource, source_id)
    if not src or src.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Source not found")
    if src.status not in ("active", "pending", "error"):
        raise HTTPException(status_code=400, detail=f"Cannot sync source in status '{src.status}'")

    pool = get_arq_pool()
    if pool:
        await pool.enqueue_job("sync_external_source_job", source_id=str(src.id))
    else:
        import asyncio
        asyncio.create_task(_sync_inline(str(src.id)))

    return {"queued": True, "source_id": str(src.id)}


async def _sync_inline(source_id: str):
    try:
        from services.arq_worker import sync_external_source_job
        await sync_external_source_job({"job_try": 1}, source_id=source_id)
    except Exception as e:
        logger.error("[integrations] inline sync failed source_id=%s err=%s", source_id, e)


# ── OAuth endpoints ────────────────────────────────────────────────────────────


@router.get("/oauth/start")
async def oauth_start(
    connector_type: str = Query(pattern=r"^(google_drive|google_calendar|gmail|notion|github)$"),
    current_user: User = Depends(get_current_user),
):
    if not fernet_ready():
        raise HTTPException(status_code=503, detail="Encryption not configured (INTEGRATION_SECRET missing)")

    conn_cls = get_connector(connector_type)

    client_id_val, client_id_var = _CLIENT_ID_MAP[connector_type]
    if not client_id_val:
        raise HTTPException(
            status_code=503,
            detail=f"{connector_type} OAuth not configured — set {client_id_var} in .env",
        )

    state = str(uuid.uuid4())

    redis = await get_redis()
    await redis.setex(
        f"intg:state:{state}",
        STATE_TTL,
        json.dumps({"user_id": current_user.id, "connector_type": connector_type}),
    )

    auth_url = conn_cls.get_auth_url(state)
    return {"url": auth_url}


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    redis = await get_redis()
    raw = await redis.get(f"intg:state:{state}")
    if not raw:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    await redis.delete(f"intg:state:{state}")

    stored = json.loads(raw)
    user_id = stored["user_id"]
    connector_type = stored["connector_type"]

    conn_cls = get_connector(connector_type)
    tokens = await conn_cls.exchange_code(code)

    credentials = {
        "access_token": encrypt_token(tokens["access_token"]),
        "expires_at": tokens.get("expires_at"),
    }
    if tokens.get("refresh_token"):
        credentials["refresh_token"] = encrypt_token(tokens["refresh_token"])

    result = await db.execute(
        select(ExternalSource).where(
            ExternalSource.user_id == user_id,
            ExternalSource.connector_type == connector_type,
            ExternalSource.resource_id.is_(None),
        )
    )
    src = result.scalar_one_or_none()
    if src:
        src.credentials = credentials
        src.status = "active"
        src.error = None
    else:
        src = ExternalSource(
            user_id=user_id,
            connector_type=connector_type,
            credentials=credentials,
            status="active",
            display_name=connector_type,
        )
        db.add(src)
    await db.commit()

    return HTMLResponse(content=HTML_RESPONSE)


# ── Calendar execute endpoint ──────────────────────────────────────────────────


class CalendarExecuteBody(BaseModel):
    op: str = Field(pattern=r"^(create|update|delete)$")
    args: dict


@router.post("/calendar/execute")
async def calendar_execute(
    body: CalendarExecuteBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from llm.tools.calendar import _calendar_create_event, _calendar_update_event, _calendar_delete_event

    try:
        if body.op == "create":
            result = await _calendar_create_event(
                db, current_user.id,
                summary=body.args["summary"],
                start=body.args["start"],
                end=body.args["end"],
                description=body.args.get("description"),
                location=body.args.get("location"),
            )
        elif body.op == "update":
            result = await _calendar_update_event(
                db, current_user.id,
                event_id=body.args["event_id"],
                summary=body.args.get("summary"),
                start=body.args.get("start"),
                end=body.args.get("end"),
                description=body.args.get("description"),
                location=body.args.get("location"),
            )
        elif body.op == "delete":
            result = await _calendar_delete_event(
                db, current_user.id,
                event_id=body.args["event_id"],
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {body.op}")
    except Exception as e:
        logger.warning("[integrations] calendar_execute failed op=%s err=%s", body.op, e)
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "summary": result}


HTML_RESPONSE = """
<!DOCTYPE html>
<html><head><script>
window.opener.postMessage({ type: 'oauth-complete' }, '*');
window.close();
</script></head><body><p>OAuth complete. You may close this window.</p></body></html>
"""
