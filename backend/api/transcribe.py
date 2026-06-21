import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth.security import get_current_user
from models import User
from services.transcribe import transcribe_audio, STUB_PLACEHOLDER

import config

router = APIRouter(prefix="/transcribe", tags=["transcribe"])
logger = logging.getLogger("api.transcribe")

MAX_AUDIO_SIZE = 25 * 1024 * 1024


@router.post("")
async def transcribe(
    file:         UploadFile = File(...),
    current_user: User       = Depends(get_current_user),
):
    if not config.VOICE_ENABLED:
        raise HTTPException(status_code=503, detail="Voice transcription is disabled")

    if file.size and file.size > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25 MB)")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")

    text = await transcribe_audio(data, file.content_type or "audio/webm")

    return {
        "text":    text,
        "backend": config.ASR_BACKEND,
        "stub":    config.ASR_BACKEND == "stub",
    }
