import logging

import config

logger = logging.getLogger("transcribe")

STUB_PLACEHOLDER = "[voice transcription stub — ASR not yet enabled]"


async def transcribe_audio(
    data: bytes,
    mime_type: str,
    *,
    language: str | None = None,
) -> str:
    backend = config.ASR_BACKEND
    try:
        if backend == "stub":
            return STUB_PLACEHOLDER
        logger.warning("Unknown ASR_BACKEND=%s, falling back to stub", backend)
        return STUB_PLACEHOLDER
    except Exception:
        logger.exception("transcribe_audio failed")
        return ""
