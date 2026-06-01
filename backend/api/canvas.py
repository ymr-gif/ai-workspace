import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.canvas_graph import (
    create_node, delete_node, get_canvas_graph,
    unwire_nodes, update_node, wire_nodes,
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
    """Return-or-create the JARVIS global conversation for this user."""
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
        )
        db.add(conv)
        await db.commit()
    return {"conversation_id": str(conv.id)}
