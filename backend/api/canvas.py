import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.canvas_graph import (
    create_node, delete_node, find_nodes, set_protected,
    get_canvas_graph, unwire_nodes, update_node, wire_nodes,
)
from auth.security import get_current_user
from core.db import get_db
from models import Conversation, User

router = APIRouter(prefix="/canvas", tags=["canvas"])
logger = logging.getLogger("canvas")


class NodeCreate(BaseModel):
    node_type: str = Field(..., min_length=1, max_length=64)
    config:    dict | None = None


class NodeUpdate(BaseModel):
    config: dict | None = None
    status: str  | None = Field(None, pattern=r"^(active|inactive|error)$")


class WireCreate(BaseModel):
    src_id:   str = Field(..., min_length=1)
    dst_id:   str = Field(..., min_length=1)
    src_port: str = Field(..., min_length=1)
    dst_port: str = Field(..., min_length=1)
    relation: str = Field("connected", min_length=1)


class WireDelete(BaseModel):
    src_id: str = Field(..., min_length=1)
    dst_id: str = Field(..., min_length=1)


@router.get("/graph")
async def canvas_graph(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    return await get_canvas_graph(current_user.id)


@router.post("/nodes", status_code=201)
async def canvas_create_node(
    body:         NodeCreate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    try:
        node_id = await create_node(current_user.id, body.node_type, body.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"node_id": node_id}


@router.patch("/nodes/{node_id}")
async def canvas_update_node(
    node_id:      str,
    body:         NodeUpdate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    try:
        await update_node(current_user.id, node_id, body.config, body.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@router.delete("/nodes/{node_id}", status_code=204)
async def canvas_delete_node(
    node_id:      str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    await delete_node(current_user.id, node_id)


@router.post("/wire", status_code=201)
async def canvas_wire(
    body:         WireCreate,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    try:
        await wire_nodes(
            current_user.id,
            body.src_id, body.dst_id,
            body.src_port, body.dst_port,
            body.relation,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.delete("/wire", status_code=204)
async def canvas_unwire(
    body:         WireDelete,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    try:
        await unwire_nodes(current_user.id, body.src_id, body.dst_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/global")
async def canvas_global(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Return-or-create the JARVIS global conversation for this user.
    Also ensures input→session canvas wiring exists."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id, Conversation.title == "JARVIS")
        .limit(1)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=current_user.id,
            title="JARVIS",
            memory_enabled=True,
            locked_model="reasoning",
        )
        db.add(conv)
        await db.commit()
    elif conv.locked_model != "reasoning":
        conv.locked_model = "reasoning"
        await db.commit()

    await _ensure_canvas_wiring(current_user.id, str(conv.id), db)
    return {"conversation_id": str(conv.id)}


async def _ensure_canvas_wiring(
    user_id: int, conversation_id: str, db: AsyncSession | None = None
) -> None:
    """Create input node + global session node and wire input→session if not already
    present. Also reaps orphaned session nodes (malformed or dead conversation_id)."""
    conv_id_str = conversation_id

    sessions = await find_nodes(user_id, "session")
    session_node = next(
        (s for s in sessions if s.get("config", {}).get("conversation_id") == conv_id_str),
        None,
    )
    if not session_node:
        # internal=True: only the bootstrap may create permanent core nodes.
        # kind="global" marks this as the permanent JARVIS session (H4) — explicit
        # identity instead of inferring "global" from the conversation_id match.
        session_id = await create_node(
            user_id, "session", {"conversation_id": conv_id_str, "kind": "global"}, internal=True
        )
    else:
        session_id = session_node["node_id"]
        if session_node.get("config", {}).get("kind") != "global":
            await update_node(user_id, session_id, {"kind": "global"})  # idempotent backfill

    inputs = await find_nodes(user_id, "input")
    if inputs:
        input_id = inputs[0]["node_id"]
    else:
        input_id = await create_node(user_id, "input", {}, internal=True)

    # core infrastructure — never deletable by the AI tool or REST (idempotent backfill)
    await set_protected(user_id, input_id, True)
    await set_protected(user_id, session_id, True)

    graph = await get_canvas_graph(user_id)
    already_wired = any(
        w["src_id"] == input_id and w["dst_id"] == session_id
        for w in graph["wires"]
    )
    if not already_wired:
        await wire_nodes(user_id, input_id, session_id, "routed_message", "message", "routes_to")

    if db is not None:
        await _reap_orphan_sessions(user_id, db, keep_node_id=session_id)


async def _reap_orphan_sessions(user_id: int, db: AsyncSession, keep_node_id: str) -> None:
    """Delete unprotected session nodes whose conversation_id is malformed or has no
    matching Postgres conversation. Never touches protected nodes or the global session.
    Self-heals canvas state on every /global load — no migration or manual cypher needed."""
    sessions = await find_nodes(user_id, "session")

    valid: dict[str, str] = {}  # conversation_id (str) -> node_id
    for s in sessions:
        node_id = s["node_id"]
        if node_id == keep_node_id or s.get("protected"):
            continue
        conv_id = (s.get("config") or {}).get("conversation_id")
        try:
            uuid.UUID(str(conv_id))
        except (ValueError, TypeError, AttributeError):
            await _prune_node(user_id, node_id, f"malformed conversation_id {conv_id!r}")
            continue
        valid[str(conv_id)] = node_id

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


async def _prune_node(user_id: int, node_id: str, reason: str) -> None:
    try:
        await delete_node(user_id, node_id)
        logger.info("[canvas] reaped orphan session %s user=%d (%s)", node_id, user_id, reason)
    except ValueError:
        pass  # protected or already gone — leave it
