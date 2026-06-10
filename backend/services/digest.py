import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import File, UserGoal, UserInsight, UserMemoryVersion

logger = logging.getLogger("services.digest")


async def build_digest(user_id: int, db: AsyncSession, days: int = 7) -> str | None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    file_count, file_names = await _new_files(user_id, db, cutoff)
    mem_count = await _memory_snapshots(user_id, db, cutoff)
    insight_count, insight_snippets = await _new_insights(user_id, db, cutoff)
    goal_updates = await _goal_activity(user_id, db, cutoff)

    if file_count == 0 and mem_count == 0 and insight_count == 0 and not goal_updates:
        return None

    lines = [f"## Your Weekly Digest — {cutoff.date()} – {datetime.now(timezone.utc).date()}", ""]

    if file_count:
        lines.append(f"### New Files ({file_count})")
        for name in file_names:
            lines.append(f"- {name}")
        lines.append("")

    if mem_count:
        lines.append(f"### Memory Snapshots ({mem_count})")
        lines.append(f"{mem_count} memory version{' was' if mem_count == 1 else 's were'} saved this week.")
        lines.append("")

    if insight_count:
        lines.append(f"### New Insights ({insight_count})")
        for s in insight_snippets:
            lines.append(f"- {s}")
        lines.append("")

    if goal_updates:
        lines.append(f"### Goal Activity ({len(goal_updates)})")
        for title, status in goal_updates:
            lines.append(f"- **{title}** — {status}")
        lines.append("")

    return "\n".join(lines)


async def _new_files(user_id: int, db: AsyncSession, cutoff: datetime) -> tuple[int, list[str]]:
    result = await db.execute(
        select(File.filename)
        .where(File.user_id == user_id, File.created_at >= cutoff)
        .order_by(File.created_at.desc())
        .limit(10)
    )
    names = result.scalars().all()
    return len(names), list(names)


async def _memory_snapshots(user_id: int, db: AsyncSession, cutoff: datetime) -> int:
    result = await db.execute(
        select(func.count()).where(
            UserMemoryVersion.user_id == user_id,
            UserMemoryVersion.created_at >= cutoff,
        )
    )
    return result.scalar() or 0


async def _new_insights(user_id: int, db: AsyncSession, cutoff: datetime) -> tuple[int, list[str]]:
    result = await db.execute(
        select(UserInsight.content)
        .where(UserInsight.user_id == user_id, UserInsight.created_at >= cutoff)
        .order_by(UserInsight.created_at.desc())
        .limit(5)
    )
    snippets = []
    for content in result.scalars().all():
        truncated = content[:120] + "…" if len(content) > 120 else content
        snippets.append(truncated)
    return len(snippets), snippets


async def _goal_activity(user_id: int, db: AsyncSession, cutoff: datetime) -> list[tuple[str, str]]:
    result = await db.execute(
        select(UserGoal.title, UserGoal.status)
        .where(UserGoal.user_id == user_id, UserGoal.updated_at >= cutoff)
        .order_by(UserGoal.updated_at.desc())
        .limit(10)
    )
    return [(row.title, row.status) for row in result.all()]
