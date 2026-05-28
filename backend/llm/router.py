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

_QUERY_FACTUAL = {
    "what is", "what are", "define", "explain", "how to", "tell me about",
    "what does", "meaning", "definition", "example", "fact", "information",
}

_QUERY_RELATIONAL = {
    "compare", "difference", "relation", "between", "versus", "vs",
    "similar", "connected", "related", "correlation", "link", "associate",
}

_QUERY_TEMPORAL = {
    "before", "after", "when", "recent", "history", "timeline", "sequence",
    "order", "earlier", "previously", "later", "since", "during", "past",
}

_QUERY_BROAD = {
    "hello", "hi", "hey", "summarize", "overview", "tell me everything",
    "what do you know", "general", "introduce", "introduction",
}


def classify(message: str) -> str:
    msg = message.lower()
    if any(kw in msg for kw in _CODER_KEYWORDS):
        return "coder"
    if any(kw in msg for kw in _REASONING_KEYWORDS):
        return "reasoning"
    return "llama"


def classify_query(message: str) -> str:
    msg = message.lower()
    if any(kw in msg for kw in _QUERY_RELATIONAL):
        return "relational"
    if any(kw in msg for kw in _QUERY_TEMPORAL):
        return "temporal"
    if any(kw in msg for kw in _QUERY_FACTUAL):
        return "factual"
    if any(kw in msg for kw in _QUERY_BROAD):
        return "broad"
    return "factual"


async def route(message: str, request_id: str) -> tuple[str, float]:
    start  = time.monotonic()
    choice = classify(message)
    model  = MODELS.get(choice, MODELS["llama"])
    latency_ms = (time.monotonic() - start) * 1000
    logger.info("[route] rid=%s model=%s latency_ms=%.2f", request_id, model, latency_ms)
    return model, latency_ms


def get_context_limit(model_name: str) -> int:
    return CONTEXT_WINDOWS.get(model_name, DEFAULT_CONTEXT_WINDOW)
