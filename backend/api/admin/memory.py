import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user, require_role
from core.db import AsyncSessionLocal, get_db
from models import Conversation, Message, User, UserMemory, UserMemoryVersion

from .utils import _audit

router = APIRouter()
logger = logging.getLogger("admin.memory")


class MemoryResetRequest(BaseModel):
    user_id: int
    level: str = "soft"
    dry_run: bool = True
    confirm: str = ""


async def _build_reset_report(user_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        mem = await db.get(UserMemory, user_id)
        sheet_content = mem.content if mem else ""

        correction_count = 0
        corr_pos = sheet_content.find("[CORRECTIONS]")
        if corr_pos != -1:
            after_corr = sheet_content[corr_pos + len("[CORRECTIONS]"):]
            import re
            next_sec = re.search(r'\[[A-Z][A-Z_]+\]', after_corr)
            if next_sec:
                corr_body = after_corr[:next_sec.start()]
            else:
                corr_body = after_corr
            if " - " in corr_body:
                parts = corr_body.split(" - ")
                correction_count = max(0, len(parts) - 1)
            elif "\n" in corr_body:
                for line in corr_body.split("\n"):
                    s = line.strip()
                    if s and not s.startswith("["):
                        correction_count += 1
            else:
                s = corr_body.strip()
                if s:
                    correction_count = 1

        conv_result = await db.execute(
            select(func.count()).select_from(Conversation)
            .where(Conversation.user_id == user_id)
        )
        total_convs = conv_result.scalar_one()

        msg_result = await db.execute(
            select(func.count()).select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
        )
        total_msgs = msg_result.scalar_one()

        tok_result = await db.execute(
            select(func.coalesce(func.sum(Message.total_tokens), 0))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
        )
        total_tokens = int(tok_result.scalar_one() or 0)

    graph_count = 0
    try:
        from core.neo4j_client import get_driver
        driver = get_driver()
        if driver:
            async with driver.session() as session:
                cnt = await session.run(
                    "MATCH (e:Entity {user_id: $uid}) RETURN count(e) AS cnt",
                    uid=user_id,
                )
                record = await cnt.single()
                graph_count = record["cnt"] if record else 0
    except Exception:
        pass

    return {
        "user_id": user_id,
        "memory_sheet_words": len(sheet_content.split()) if sheet_content else 0,
        "memory_correction_entries": correction_count,
        "conversation_count": total_convs,
        "message_count": total_msgs,
        "total_tokens": total_tokens,
        "graph_entities": graph_count,
    }


async def _backup_user(user_id: int) -> None:
    backup_dir = Path("storage/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    async with AsyncSessionLocal() as db:
        mem = await db.get(UserMemory, user_id)
        if mem and mem.content:
            db.add(UserMemoryVersion(
                user_id=user_id,
                version=mem.version,
                content=mem.content or "",
                project_summary=mem.project_summary or "",
            ))
            await db.commit()
            logger.info("[backup] memory version snapshot user_id=%s version=%d", user_id, mem.version)

        try:
            from api.export import _build_zip
            zip_buf = await _build_zip(user_id, db)
            backup_path = backup_dir / f"backup_{user_id}_{ts}.zip"
            zip_buf.seek(0)
            import aiofiles
            async with aiofiles.open(str(backup_path), "wb") as f:
                await f.write(zip_buf.read())
            logger.info("[backup] export zip saved user_id=%s path=%s", user_id, backup_path)
        except Exception:
            logger.exception("[backup] export zip failed user_id=%s", user_id)

    try:
        from core.neo4j_client import get_driver
        driver = get_driver()
        if driver:
            async with driver.session() as session:
                result = await session.run(
                    "MATCH (e:Entity {user_id: $uid}) "
                    "OPTIONAL MATCH (e)-[r:RELATED_TO]->(other:Entity {user_id: $uid}) "
                    "RETURN e.name AS name, e.type AS type, "
                    "       collect({rel: r.type, target: other.name}) AS rels",
                    uid=user_id,
                )
                rows = await result.data()
                if rows:
                    graph_path = backup_dir / f"graph_{user_id}_{ts}.json"
                    async with aiofiles.open(str(graph_path), "w") as f:
                        await f.write(json.dumps(rows, indent=2, default=str))
                    logger.info("[backup] graph dump saved user_id=%s", user_id)
    except Exception:
        logger.exception("[backup] graph dump failed user_id=%s", user_id)


async def _purge_canvas_entities(user_id: int) -> int:
    try:
        from core.neo4j_client import get_driver
        driver = get_driver()
        if not driver:
            return 0
        async with driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity {user_id: $uid}) "
                "WHERE e.name =~ $pattern "
                "DETACH DELETE e "
                "RETURN count(e) AS cnt",
                uid=user_id,
                pattern="(?i).*(canvas|session node|workspace|output node|input node).*",
            )
            record = await result.single()
            purged = record["cnt"] if record else 0
        if purged > 0:
            from llm.graph_memory import _cache_del_user
            await _cache_del_user(user_id)
        return purged
    except Exception:
        logger.exception("[reset] graph canvas purge failed user_id=%s", user_id)
        return 0


async def _soft_reset(user_id: int) -> dict:
    from llm.summarizer.compact import _prune_canvas_corrections
    from llm.graph_memory import merge_duplicate_entities, _cache_del_user

    pruned_count = 0
    archive_count = 0

    async with AsyncSessionLocal() as db:
        mem = await db.get(UserMemory, user_id)
        if mem and mem.content:
            cleaned = _prune_canvas_corrections(mem.content)
            if cleaned != mem.content:
                db.add(UserMemoryVersion(
                    user_id=user_id,
                    version=mem.version,
                    content=mem.content or "",
                    project_summary=mem.project_summary or "",
                ))
                mem.content = cleaned
                mem.version += 1
                mem.updated_at = datetime.now(timezone.utc)
                await db.commit()
                pruned_count = 1
                logger.info("[reset] pruned Canvas corrections user_id=%s", user_id)

        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.is_archived == False,
            )
        )
        active_convs = conv_result.scalars().all()
        now = datetime.now(timezone.utc)

        for conv in active_convs:
            age_days = (now - conv.updated_at).days
            msg_cnt = await db.execute(
                select(func.count()).select_from(Message)
                .where(Message.conversation_id == conv.id)
            )
            total_msgs = msg_cnt.scalar_one()
            tok_result = await db.execute(
                select(func.coalesce(func.sum(Message.total_tokens), 0))
                .where(Message.conversation_id == conv.id)
            )
            total_tok = int(tok_result.scalar_one() or 0)

            if total_msgs > 80 or total_tok > 120000 or age_days > 3:
                conv.is_archived = True
                conv.archived_at = now
                archive_count += 1

        if archive_count > 0:
            await db.commit()

    graph_canvas_purged = await _purge_canvas_entities(user_id)
    graph_merged = await merge_duplicate_entities(user_id)

    return {
        "corrections_pruned": pruned_count,
        "conversations_archived": archive_count,
        "graph_canvas_purged": graph_canvas_purged,
        "graph_duplicates_merged": graph_merged,
    }


async def _hard_reset(user_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        mem = await db.get(UserMemory, user_id)
        if mem:
            db.add(UserMemoryVersion(
                user_id=user_id,
                version=mem.version,
                content=mem.content or "",
                project_summary=mem.project_summary or "",
            ))
            mem.content = "[USER]\n"
            mem.project_summary = ""
            mem.version += 1
            mem.salience = 0.0
            mem.confidence = 0.0
            mem.fact_saliences = {}
            mem.updated_at = datetime.now(timezone.utc)

        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.is_archived == False,
            )
        )
        now = datetime.now(timezone.utc)
        archive_count = 0
        for conv in conv_result.scalars().all():
            conv.is_archived = True
            conv.archived_at = now
            archive_count += 1

        await db.commit()

    try:
        from core.neo4j_client import get_driver
        driver = get_driver()
        if driver:
            async with driver.session() as session:
                await session.run(
                    "MATCH (e:Entity {user_id: $uid}) DETACH DELETE e",
                    uid=user_id,
                )
                from llm.graph_memory import _cache_del_user
                await _cache_del_user(user_id)
    except Exception:
        logger.exception("[reset] graph clear failed user_id=%s", user_id)

    return {
        "memory_cleared": True,
        "conversations_archived": archive_count,
        "graph_entities_cleared": True,
    }


@router.post("/memory/reset")
async def memory_reset(
    body: MemoryResetRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    user = await db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not body.dry_run and body.confirm != f"RESET {body.user_id}":
        raise HTTPException(status_code=400, detail="Invalid confirmation. Use confirm=\"RESET <user_id>\"")

    report = await _build_reset_report(body.user_id)

    if body.dry_run:
        return {"dry_run": True, "report": report}

    await _backup_user(body.user_id)

    if body.level == "hard":
        result = await _hard_reset(body.user_id)
    else:
        result = await _soft_reset(body.user_id)

    await _audit(db, admin, f"memory.reset.{body.level}",
                 target_user_id=body.user_id, detail={**report, **result})
    await db.commit()

    return {"ok": True, "level": body.level, "result": result}
