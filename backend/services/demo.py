"""Ephemeral per-login demo accounts.

Every login as the public `demo` seed account mints a fresh, isolated
`demo_<rand>` account instead of authenticating the shared seed. Two
reviewers a few minutes apart get two independent sandboxes. Idle
ephemerals are purged by `reap_idle_demos` (called from
`services/scheduler_worker.py` on an interval). Spend is bounded both
per-account (`User.cost_limit_usd`, enforced by the existing
`_check_cost_cap`) and globally across the whole `demo_*` pool
(`pool_spend_usd`, enforced here and at login-mint time).

All config is read as `config.X` at call time (never `from config import`)
so `/admin/env/reload` reaches this module live — see backend/CLAUDE.md
`LLM_BACKEND` invariant for why that matters.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from redis.exceptions import RedisError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from core.redis_client import get_redis
from models import Conversation, File, FileChunk, Message, User

logger = logging.getLogger("demo")

_POOL_CACHE_KEY = "demo:pool:spend"
_POOL_CACHE_TTL = 30  # seconds


def is_ephemeral_demo(username: str) -> bool:
    """A minted ephemeral demo account — never the seed `demo` login itself."""
    return username.startswith("demo_")


async def pool_spend_usd(db: AsyncSession) -> float:
    """Total assistant-message spend across all `demo_*` accounts in the
    rolling global window (`DEMO_GLOBAL_WINDOW_HOURS`). Redis-cached (TTL
    ~30s) when USE_REDIS; falls back to a live query otherwise or on a
    Redis miss/error.
    """
    if config.USE_REDIS:
        try:
            cached = await get_redis().get(_POOL_CACHE_KEY)
            if cached is not None:
                return float(cached)
        except (RedisError, ValueError):
            pass

    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.DEMO_GLOBAL_WINDOW_HOURS)
    q = (
        select(func.coalesce(func.sum(Message.cost_usd), 0.0))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(User, User.id == Conversation.user_id)
        .where(
            User.username.like(r"demo\_%", escape="\\"),
            Message.role == "assistant",
            Message.created_at >= cutoff,
        )
    )
    total = float((await db.execute(q)).scalar_one() or 0.0)

    if config.USE_REDIS:
        try:
            await get_redis().set(_POOL_CACHE_KEY, str(total), ex=_POOL_CACHE_TTL)
        except RedisError:
            pass

    return total


async def count_live_demo_accounts(db: AsyncSession) -> int:
    """Row-count guard, disabled by default (`DEMO_MAX_LIVE_ACCOUNTS=0`)."""
    q = select(func.count()).select_from(User).where(User.username.like(r"demo\_%", escape="\\"))
    return int((await db.execute(q)).scalar_one() or 0)


async def mint_ephemeral_demo(db: AsyncSession) -> User:
    """Create a fresh isolated `demo_<rand>` account. The password hash is
    random and discarded immediately — this account is never a direct
    login target, only reachable via the seed-login mint path.

    `hash_password` is imported here, not at module level: `auth/__init__.py`
    imports `auth.router`, which imports this module — a top-level
    `from auth.security import hash_password` here closes that into a real
    circular import whenever something reaches `services.demo` before `auth`
    has started loading (e.g. `api/chat/helpers.py`, imported earlier than
    `auth` in `main.py`). Deferring to call time sidesteps it entirely.
    """
    from auth.security import hash_password

    username = f"demo_{secrets.token_hex(6)}"
    user = User(
        username=username,
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role="user",
        is_active=True,
        cost_limit_usd=config.DEMO_PER_ACCOUNT_CAP_USD,
        cost_window_days=config.DEMO_PER_ACCOUNT_WINDOW_DAYS,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _purge_demo_user(db: AsyncSession, user_id: int) -> None:
    """Delete one demo account and its non-cascading externals.

    `users.id` child FKs are `ondelete="CASCADE"` for every table EXCEPT
    `files.user_id` (no ondelete action) — its child `file_chunks.file_id`
    also has none, so both must be deleted explicitly before the User row,
    same as the existing manual-delete path in `api/files/router.py`.
    Neo4j graph entities and on-disk file blobs are external to Postgres
    entirely and would leak silently if not cleaned here.
    """
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
        logger.exception("[demo] graph purge failed user_id=%s", user_id)

    files = (await db.execute(select(File).where(File.user_id == user_id))).scalars().all()
    for f in files:
        await db.execute(delete(FileChunk).where(FileChunk.file_id == f.id))
        try:
            Path(f.storage_path).unlink(missing_ok=True)
        except Exception:
            pass
    if files:
        await db.execute(delete(File).where(File.user_id == user_id))

    user = await db.get(User, user_id)
    if user:
        await db.delete(user)
    await db.commit()


async def reap_idle_demos(db: AsyncSession) -> int:
    """Purge `demo_*` accounts idle past `DEMO_IDLE_TTL_HOURS`.

    Idle = no message in any of their conversations more recent than the
    cutoff, falling back to `User.created_at` for an account that never
    sent one. Returns the count purged.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.DEMO_IDLE_TTL_HOURS)

    last_activity = (
        select(
            Conversation.user_id.label("user_id"),
            func.max(Message.created_at).label("last_msg_at"),
        )
        .join(Message, Message.conversation_id == Conversation.id)
        .group_by(Conversation.user_id)
        .subquery()
    )
    q = (
        select(User, last_activity.c.last_msg_at)
        .outerjoin(last_activity, last_activity.c.user_id == User.id)
        .where(User.username.like(r"demo\_%", escape="\\"))
    )
    rows = (await db.execute(q)).all()

    reaped = 0
    for user, last_msg_at in rows:
        last_active = last_msg_at or user.created_at
        if last_active is not None and last_active < cutoff:
            await _purge_demo_user(db, user.id)
            reaped += 1

    return reaped
