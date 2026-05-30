import asyncio
import io
import json
import logging
from pathlib import Path
import re
import zipfile

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import Conversation, File, Message, User, UserMemory, UserMemoryVersion

router = APIRouter(prefix="/export", tags=["export"])
logger = logging.getLogger("export")


def _safe_filename(title: str, ext: str = "md") -> str:
    safe = re.sub(r'[\"\\/\r\n\x00-\x1f]', '', title)[:40].strip() or "conversation"
    return f"{safe}.{ext}"


async def _build_zip(user_id: int, db: AsyncSession) -> io.BytesIO:
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # ── conversations ──────────────────────────────────────────
        conv_result = await db.execute(
            select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.created_at)
        )
        conversations = conv_result.scalars().all()

        for conv in conversations:
            msg_result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at.asc())
            )
            msgs = msg_result.scalars().all()

            md_lines = [f"# {conv.title}\n\n"]
            for m in msgs:
                label = "**User:**" if m.role == "user" else f"**AI** ({m.model or 'unknown'}):"
                md_lines.append(f"{label}\n\n{m.content}\n\n---\n\n")

            conv_filename = f"conversations/{conv.id}_{_safe_filename(conv.title)}"
            zf.writestr(conv_filename, "".join(md_lines))

        # ── files ──────────────────────────────────────────────────
        file_result = await db.execute(
            select(File).where(File.user_id == user_id)
        )
        files = file_result.scalars().all()

        for f in files:
            try:
                path = Path(f.storage_path)
                if path.exists():
                    content = await _read_file(path)
                    zf.writestr(f"files/{f.filename}", content)
            except Exception:
                logger.warning("[export] failed to read file %s id=%s", f.filename, f.id)

        # ── memory sheet ───────────────────────────────────────────
        mem_result = await db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        memory = mem_result.scalar_one_or_none()
        if memory and memory.content:
            zf.writestr("memory/sheet.txt", memory.content)

        # ── memory versions ────────────────────────────────────────
        ver_result = await db.execute(
            select(UserMemoryVersion)
            .where(UserMemoryVersion.user_id == user_id)
            .order_by(UserMemoryVersion.version.asc())
        )
        versions = ver_result.scalars().all()
        for v in versions:
            if v.content:
                zf.writestr(f"memory/versions/{v.version}.txt", v.content)

        # ── graph entities ─────────────────────────────────────────
        try:
            from core.neo4j_client import get_driver

            driver = get_driver()
            if driver:
                async with driver.session() as session:
                    result = await session.run(
                        "MATCH (e:Entity {user_id: $uid}) "
                        "RETURN e.name AS name, e.type AS type, e.updated_at AS updated_at "
                        "ORDER BY e.updated_at DESC LIMIT 500",
                        uid=user_id,
                    )
                    rows = await result.data()
                    if rows:
                        zf.writestr("graph/entities.json", json.dumps(rows, indent=2, default=str))
        except Exception:
            logger.warning("[export] graph dump skipped — unavailable")

    buf.seek(0)
    return buf


async def _read_file(path: Path) -> bytes:
    return await asyncio.to_thread(_sync_read, path)


def _sync_read(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


@router.get("/full")
async def export_full(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    zip_buf = await _build_zip(current_user.id, db)
    return StreamingResponse(
        iter([zip_buf.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=export.zip",
            "Content-Length": str(zip_buf.tell()),
        },
    )
