import uuid
from datetime import datetime, timezone

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import ScheduledPrompt, ScheduledPromptRun, User

router = APIRouter(prefix="/scheduled-prompts", tags=["scheduled-prompts"])


def _next_run(cron_expr: str) -> datetime:
    return croniter(cron_expr, datetime.now(timezone.utc)).get_next(datetime)


def _schedule_row(s: ScheduledPrompt) -> dict:
    return {
        "id":             str(s.id),
        "name":           s.name,
        "prompt":         s.prompt,
        "cron_expr":      s.cron_expr,
        "model_override": s.model_override,
        "is_active":      s.is_active,
        "last_run_at":    s.last_run_at.isoformat()  if s.last_run_at  else None,
        "next_run_at":    s.next_run_at.isoformat()  if s.next_run_at  else None,
        "created_at":     s.created_at.isoformat(),
    }


def _run_row(r: ScheduledPromptRun) -> dict:
    return {
        "id":             str(r.id),
        "started_at":     r.started_at.isoformat(),
        "completed_at":   r.completed_at.isoformat() if r.completed_at else None,
        "status":         r.status,
        "output_file_id": str(r.output_file_id) if r.output_file_id else None,
        "error":          r.error,
    }


class ScheduleCreate(BaseModel):
    name:           str = Field(..., min_length=1, max_length=100)
    prompt:         str = Field(..., min_length=1)
    cron_expr:      str = Field(..., min_length=1, max_length=100)
    model_override: str | None = None

    @field_validator("cron_expr")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v!r}")
        return v


class SchedulePatch(BaseModel):
    name:           str | None = Field(None, min_length=1, max_length=100)
    prompt:         str | None = Field(None, min_length=1)
    cron_expr:      str | None = Field(None, min_length=1, max_length=100)
    model_override: str | None = None
    is_active:      bool | None = None

    @field_validator("cron_expr")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is not None and not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v!r}")
        return v


@router.post("", status_code=201)
async def create_schedule(
    body:         ScheduleCreate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    s = ScheduledPrompt(
        user_id        = current_user.id,
        name           = body.name.strip(),
        prompt         = body.prompt,
        cron_expr      = body.cron_expr,
        model_override = body.model_override,
        next_run_at    = _next_run(body.cron_expr),
    )
    db.add(s)
    await db.commit()
    return _schedule_row(s)


@router.get("")
async def list_schedules(
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(ScheduledPrompt)
        .where(ScheduledPrompt.user_id == current_user.id)
        .order_by(ScheduledPrompt.created_at.desc())
    )
    return [_schedule_row(s) for s in result.scalars().all()]


@router.get("/{schedule_id}")
async def get_schedule(
    schedule_id:  str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        sid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    s = await db.get(ScheduledPrompt, sid)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    runs = (await db.execute(
        select(ScheduledPromptRun)
        .where(ScheduledPromptRun.scheduled_prompt_id == sid)
        .order_by(ScheduledPromptRun.started_at.desc())
        .limit(20)
    )).scalars().all()

    return {**_schedule_row(s), "recent_runs": [_run_row(r) for r in runs]}


@router.patch("/{schedule_id}")
async def patch_schedule(
    schedule_id:  str,
    body:         SchedulePatch,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        sid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    s = await db.get(ScheduledPrompt, sid)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    updated = body.model_dump(exclude_unset=True)
    if "name"           in updated: s.name           = body.name.strip()
    if "prompt"         in updated: s.prompt         = body.prompt
    if "model_override" in updated: s.model_override = body.model_override
    if "is_active"      in updated: s.is_active      = body.is_active
    if "cron_expr"      in updated:
        s.cron_expr   = body.cron_expr
        s.next_run_at = _next_run(body.cron_expr)

    await db.commit()
    return _schedule_row(s)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id:  str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        sid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    s = await db.get(ScheduledPrompt, sid)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    await db.delete(s)
    await db.commit()


@router.get("/{schedule_id}/runs")
async def list_runs(
    schedule_id:  str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    try:
        sid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    s = await db.get(ScheduledPrompt, sid)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    runs = (await db.execute(
        select(ScheduledPromptRun)
        .where(ScheduledPromptRun.scheduled_prompt_id == sid)
        .order_by(ScheduledPromptRun.started_at.desc())
        .limit(20)
    )).scalars().all()

    return [_run_row(r) for r in runs]


@router.post("/{schedule_id}/run", status_code=202)
async def trigger_run(
    schedule_id:  str,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
):
    """Trigger an immediate manual run. Returns run id; execution is async."""
    import asyncio
    from services.scheduler_worker import execute_scheduled_prompt

    try:
        sid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    s = await db.get(ScheduledPrompt, sid)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    run = ScheduledPromptRun(
        scheduled_prompt_id = sid,
        started_at          = datetime.now(timezone.utc),
        status              = "running",
    )
    db.add(run)
    await db.commit()

    asyncio.create_task(execute_scheduled_prompt(sid, run.id))
    return {"ok": True, "run_id": str(run.id)}
