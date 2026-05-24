import logging

import llm.client as llm_client
from config import NVIDIA_API_KEY, NIM_EMBEDDING_URL, MODEL_EMBEDDING

logger = logging.getLogger("embeddings")


async def embed(text: str, input_type: str = "passage") -> list[float] | None:
    if llm_client.client is None:
        logger.warning("[embeddings] HTTP client not initialized")
        return None
    try:
        resp = await llm_client.client.post(
            NIM_EMBEDDING_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":           MODEL_EMBEDDING,
                "input":           [text[:2000]],
                "input_type":      input_type,
                "encoding_format": "float",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except Exception as e:
        logger.warning("[embeddings] embed failed: %s", e)
        return None
