import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user
from core.db import get_db
from models import Conversation, ConversationFile, File as FileModel, User

logger = logging.getLogger("conversations")
router = APIRouter()


@router.get("/conversations/{conversation_id}/files")
async def get_conversation_files(
    conversation_id: str,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    conv = await db.get(Conversation, cid)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    result = await db.execute(
        select(FileModel)
        .join(ConversationFile, FileModel.id == ConversationFile.file_id)
        .where(ConversationFile.conversation_id == cid)
    )
    files = result.scalars().all()
    return [
        {
            "id":       str(f.id),
            "filename": f.filename,
            "status":   f.upload_status,
        }
        for f in files
    ]


class AttachFileRequest(BaseModel):
    file_id: str


@router.post("/conversations/{conversation_id}/files", status_code=201)
async def attach_file(
    conversation_id: str,
    body:            AttachFileRequest,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    try:
        cid = uuid.UUID(conversation_id)
        fid = uuid.UUID(body.file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")

    conv = await db.get(Conversation, cid)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    f = await db.get(FileModel, fid)
    if not f or f.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    existing = await db.get(ConversationFile, (cid, fid))
    if not existing:
        db.add(ConversationFile(conversation_id=cid, file_id=fid))
        await db.commit()

    return {"ok": True}


@router.delete("/conversations/{conversation_id}/files/{file_id}")
async def detach_file(
    conversation_id: str,
    file_id:         str,
    db:              AsyncSession = Depends(get_db),
    current_user:    User         = Depends(get_current_user),
):
    try:
        cid = uuid.UUID(conversation_id)
        fid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    conv = await db.get(Conversation, cid)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")

    cf = await db.get(ConversationFile, (cid, fid))
    if cf:
        await db.delete(cf)
        await db.commit()

    return {"ok": True}
