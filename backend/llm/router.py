import logging
import time

from config import CONTEXT_WINDOWS, DEFAULT_CONTEXT_WINDOW, MODELS

logger = logging.getLogger("router")

_CODER_KEYWORDS = {
    "code", "error", "bug", "fix", "debug", "function", "class", "implement",
    "write a", "script", "program", "algorithm", "syntax", "compile", "refactor",
    "import", "library", "api", "sql", "query", "regex",
}

_REASONING_KEYWORDS = {
    "why", "explain", "how does", "how do", "what is", "what are", "compare",
    "difference", "analyze", "analyse", "reason", "cause", "effect", "theory",
    "concept", "understand", "depth", "detail",
}


def classify(message: str) -> str:
    msg = message.lower()
    if any(kw in msg for kw in _CODER_KEYWORDS):
        return "coder"
    if any(kw in msg for kw in _REASONING_KEYWORDS):
        return "reasoning"
    return "llama"


async def route(message: str, request_id: str) -> tuple[str, float]:
    start  = time.monotonic()
    choice = classify(message)
    model  = MODELS.get(choice, MODELS["llama"])
    latency_ms = (time.monotonic() - start) * 1000
    logger.info("[route] rid=%s model=%s latency_ms=%.2f", request_id, model, latency_ms)
    return model, latency_ms


def get_context_limit(model_name: str) -> int:
    return CONTEXT_WINDOWS.get(model_name, DEFAULT_CONTEXT_WINDOW)
