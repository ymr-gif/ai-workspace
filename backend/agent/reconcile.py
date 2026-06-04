from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from agent.canvas_graph import delete_node, find_nodes, set_protected
from agent.node import PERMANENT_TYPES
from core.neo4j_client import get_driver
from models import Conversation

logger = logging.getLogger("canvas_reconcile")


async def list_canvas_user_ids() -> list[int]:
    driver = get_driver()
    if not driver:
        return []
    async with driver.session() as session:
        result = await session.run("MATCH (n:CanvasNode) RETURN DISTINCT n.user_id AS uid")
        rows = await result.data()
    return [r["uid"] for r in rows if r.get("uid") is not None]


async def _prune_node(
    user_id: int, node_id: str, reason: str, force: bool = False
) -> None:
    try:
        await delete_node(user_id, node_id)
    except ValueError:
        if not force:
            return
        await set_protected(user_id, node_id, False)
        try:
            await delete_node(user_id, node_id)
        except ValueError:
            return
    logger.info("[canvas] reconcile pruned %s user=%d (%s)", node_id, user_id, reason)


async def _reap_orphan_sessions(user_id: int, db) -> None:
    sessions = await find_nodes(user_id, "session")

    valid: dict[str, str] = {}
    for s in sessions:
        if s.get("protected"):
            continue
        conv_id = (s.get("config") or {}).get("conversation_id")
        try:
            uuid.UUID(str(conv_id))
        except (ValueError, TypeError, AttributeError):
            await _prune_node(user_id, s["node_id"], f"malformed conversation_id {conv_id!r}")
            continue
        valid[str(conv_id)] = s["node_id"]

    if not valid:
        return

    rows = await db.execute(
        select(Conversation.id).where(
            Conversation.user_id == user_id,
            Conversation.id.in_([uuid.UUID(c) for c in valid]),
        )
    )
    existing = {str(r) for r in rows.scalars().all()}
    for conv_id, node_id in valid.items():
        if conv_id not in existing:
            await _prune_node(user_id, node_id, "no matching conversation")


async def _collapse_duplicate_nodes(user_id: int) -> None:
    for node_type in PERMANENT_TYPES:
        nodes = await find_nodes(user_id, node_type)
        if len(nodes) <= 1:
            continue
        keep = next((n for n in nodes if n.get("protected")), nodes[0])["node_id"]
        for n in nodes:
            if n["node_id"] != keep:
                await _prune_node(user_id, n["node_id"], f"duplicate {node_type}", force=True)

    seen: dict[str, dict] = {}
    for n in await find_nodes(user_id, "session"):
        conv = (n.get("config") or {}).get("conversation_id")
        if conv is None:
            continue
        if conv not in seen:
            seen[conv] = n
            continue
        prev = seen[conv]
        if n.get("protected") and not prev.get("protected"):
            await _prune_node(user_id, prev["node_id"], f"duplicate session conv={conv}", force=True)
            seen[conv] = n
        else:
            await _prune_node(user_id, n["node_id"], f"duplicate session conv={conv}", force=True)


async def reconcile_canvas(user_id: int, db) -> None:
    await _reap_orphan_sessions(user_id, db)
    await _collapse_duplicate_nodes(user_id)
