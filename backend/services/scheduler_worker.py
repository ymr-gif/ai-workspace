"""Standalone scheduler worker — runs APScheduler jobs for ScheduledPrompt rows."""
import asyncio
import logging
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter
from sqlalchemy import select

import llm.client as llm_client
from agent.canvas_graph import list_canvas_user_ids, reconcile_canvas
from config import BACKUP_SCHEDULE, MODELS, REQUEST_TIMEOUT
from core.db import AsyncSessionLocal, init_db
from core.logger import setup_logging
from core.neo4j_client import close_neo4j, init_neo4j
from llm.nim import call as nim_call
from models import File as FileModel, ScheduledPrompt, ScheduledPromptRun, UserMemory
from services.processor import process_file_async
from storage.storage_manager import StorageManager

setup_logging()
logger = logging.getLogger("scheduler")

_storage = StorageManager()


async def execute_scheduled_prompt(
    schedule_id: uuid.UUID,
    run_id:      uuid.UUID,
) -> None:
    """Run a single scheduled prompt and persist the result as a File."""
    async with AsyncSessionLocal() as db:
        s   = await db.get(ScheduledPrompt, schedule_id)
        run = await db.get(ScheduledPromptRun, run_id)
        if not s or not run:
            return

        try:
            model = s.model_override or MODELS["llama"]
            result = await nim_call(
                model    = model,
                messages = [{"role": "user", "content": s.prompt}],
                request_id = str(run_id),
            )

            if not result.get("ok"):
                raise RuntimeError(result.get("error", "NIM call failed"))

            content  = result["content"]
            ts       = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{s.name}_{ts}.txt".replace(" ", "_")

            storage_path, size_bytes, sha256 = await _storage.save_text(content, filename)

            file_record = FileModel(
                user_id      = s.user_id,
                filename     = filename,
                mime_type    = "text/plain",
                size_bytes   = size_bytes,
                storage_path = storage_path,
                upload_status= "uploaded",
                sha256_hash  = sha256,
            )
            db.add(file_record)
            await db.flush()

            asyncio.create_task(process_file_async(file_record.id, storage_path, "text/plain"))

            run.status         = "success"
            run.completed_at   = datetime.now(timezone.utc)
            run.output_file_id = file_record.id
            s.last_run_at      = run.completed_at
            s.next_run_at      = croniter(s.cron_expr, run.completed_at).get_next(datetime)
            await db.commit()
            logger.info("[scheduler] run=%s schedule=%s status=success file=%s", run_id, schedule_id, file_record.id)

        except Exception as e:
            logger.exception("[scheduler] run=%s schedule=%s failed", run_id, schedule_id)
            run.status       = "error"
            run.error        = str(e)[:2000]
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()


async def _fire(schedule_id: uuid.UUID) -> None:
    """APScheduler callback — creates a run record then delegates to execute_."""
    async with AsyncSessionLocal() as db:
        s = await db.get(ScheduledPrompt, schedule_id)
        if not s or not s.is_active:
            return
        run = ScheduledPromptRun(
            scheduled_prompt_id = schedule_id,
            started_at          = datetime.now(timezone.utc),
            status              = "running",
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    asyncio.create_task(execute_scheduled_prompt(schedule_id, run_id))


async def sync_schedules(scheduler: AsyncIOScheduler) -> None:
    """Load all active schedules from DB, add/remove APScheduler jobs to match."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScheduledPrompt).where(ScheduledPrompt.is_active == True)
        )
        schedules = result.scalars().all()

    active_ids = {str(s.id) for s in schedules}
    existing   = {job.id for job in scheduler.get_jobs()}

    # Remove stale jobs
    for job_id in existing - active_ids:
        scheduler.remove_job(job_id)
        logger.info("[scheduler] removed job %s", job_id)

    # Add new jobs
    for s in schedules:
        sid = str(s.id)
        if sid not in existing:
            try:
                trigger = CronTrigger.from_crontab(s.cron_expr, timezone="UTC")
                scheduler.add_job(
                    _fire,
                    trigger = trigger,
                    id      = sid,
                    args    = [s.id],
                    replace_existing = True,
                )
                logger.info("[scheduler] scheduled job %s cron=%s", sid, s.cron_expr)
            except Exception as e:
                logger.warning("[scheduler] invalid cron for %s: %s", sid, e)

    logger.info("[scheduler] synced — active=%d scheduled=%d", len(schedules), len(scheduler.get_jobs()))


async def run_memory_compaction() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserMemory).where(UserMemory.content.isnot(None)))
        rows = result.scalars().all()

    from core.arq_pool import get_arq_pool
    pool = get_arq_pool()
    if not pool:
        logger.warning("[scheduler] compaction skipped — no arq pool")
        return

    count = 0
    for row in rows:
        if len(row.content.split()) >= 100:
            await pool.enqueue_job("compact_memory_job", row.user_id)
            count += 1

    logger.info("[scheduler] compaction queued for %d users", count)


async def run_canvas_reconcile() -> None:
    """Periodic canvas hygiene for every user — reaps orphan sessions and collapses
    duplicate nodes that predate the create_node dedup guard. Idempotent."""
    try:
        user_ids = await list_canvas_user_ids()
    except Exception as e:
        logger.warning("[scheduler] canvas reconcile: could not list users: %s", e)
        return

    done = 0
    for uid in user_ids:
        try:
            async with AsyncSessionLocal() as db:
                await reconcile_canvas(uid, db)
            done += 1
        except Exception:
            logger.exception("[scheduler] canvas reconcile failed user=%s", uid)
    logger.info("[scheduler] canvas reconcile complete — %d users", done)


async def run_backup() -> None:
    script = Path(__file__).resolve().parent.parent.parent / "docker" / "backup.sh"
    logger.info("[backup] starting — %s", script)
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", str(script),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logger.info("[backup] success — %s", stdout.decode().strip())
        else:
            logger.warning("[backup] failed (rc=%d) — %s", proc.returncode, stderr.decode().strip())
    except Exception as e:
        logger.exception("[backup] exception — %s", e)


async def main() -> None:
    logger.info("[scheduler] starting up")
    await init_db()
    await init_neo4j()

    llm_client.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    logger.info("[scheduler] http client ready")

    scheduler = AsyncIOScheduler(timezone="UTC")
    await sync_schedules(scheduler)

    # Re-sync every 5 minutes to pick up new/modified/deleted schedules
    scheduler.add_job(
        lambda: asyncio.create_task(sync_schedules(scheduler)),
        "interval",
        minutes = 5,
        id      = "__sync__",
    )

    # Daily memory compaction at 3 AM UTC
    scheduler.add_job(
        lambda: asyncio.create_task(run_memory_compaction()),
        CronTrigger.from_crontab("0 3 * * *", timezone="UTC"),
        id = "__compact_memory__",
    )

    # Canvas reconcile every 6 hours — reap orphans + collapse duplicates
    scheduler.add_job(
        lambda: asyncio.create_task(run_canvas_reconcile()),
        "interval",
        hours = 6,
        id    = "__canvas_reconcile__",
    )

    # Scheduled backup via BACKUP_SCHEDULE env (default: 2 AM UTC)
    try:
        scheduler.add_job(
            lambda: asyncio.create_task(run_backup()),
            CronTrigger.from_crontab(BACKUP_SCHEDULE, timezone="UTC"),
            id = "__backup__",
        )
        logger.info("[scheduler] backup scheduled cron=%s", BACKUP_SCHEDULE)
    except Exception as e:
        logger.warning("[scheduler] invalid backup schedule %s: %s", BACKUP_SCHEDULE, e)

    scheduler.start()
    logger.info("[scheduler] running")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("[scheduler] shutting down")
        scheduler.shutdown(wait=False)
        if llm_client.client:
            await llm_client.client.aclose()
        await close_neo4j()


if __name__ == "__main__":
    asyncio.run(main())
