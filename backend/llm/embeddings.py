import logging

import llm.client as llm_client
import config

logger = logging.getLogger("embeddings")


async def embed(text: str, input_type: str = "passage") -> list[float] | None:
    if llm_client.client is None:
        logger.error("[embeddings] HTTP client not initialized")
        return None
    try:
        headers = {"Content-Type": "application/json"}
        if config.NVIDIA_API_KEY:
            headers["Authorization"] = f"Bearer {config.NVIDIA_API_KEY}"
        resp = await llm_client.client.post(
            config.NIM_EMBEDDING_URL,
            headers=headers,
            json={
                "model":           config.MODEL_EMBEDDING,
                "input":           [text[:2000]],
                "input_type":      input_type,
                "encoding_format": "float",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except Exception as e:
        logger.error("[embeddings] embed failed: %s", e)
        return None
