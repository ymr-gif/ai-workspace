from __future__ import annotations

from sqlalchemy import select, update

from core.db import AsyncSessionLocal
from models.user import UserMemory


async def get_scratchpad(user_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserMemory.agent_scratchpad).where(UserMemory.user_id == user_id)
        )
        val = result.scalar()
        return val or {}


async def update_scratchpad(user_id: int, scratchpad: dict) -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(UserMemory.agent_scratchpad).where(UserMemory.user_id == user_id)
        )
        current = existing.scalar() or {}
        merged = {**current, **scratchpad}
        await db.execute(
            update(UserMemory)
            .where(UserMemory.user_id == user_id)
            .values(agent_scratchpad=merged)
        )
        await db.commit()
