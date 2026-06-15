import logging
import time

from config import CONTEXT_WINDOWS, DEFAULT_CONTEXT_WINDOW, MODELS

logger = logging.getLogger("router")

# --- User-intent classification (Reasoning Loop, Dimension 3) ----------------
# Distinct from classify()/classify_query(): this asks WHAT the user is trying to
# do — act on something (task), range over a topic (exploration), or get an
# answer (question). Feeds retrieval breadth + tool eagerness, not model choice.
_INTENT_TASK = {
    "create", "build", "make", "add", "update", "edit", "change", "modify",
    "delete", "remove", "fix", "implement", "write a", "write the", "generate",
    "run", "execute", "schedule", "send", "rename", "patch", "append", "refactor",
    "set up", "configure", "install", "deploy",
}
_INTENT_EXPLORE = {
    "show me everything", "what do you know", "tell me everything", "brainstorm",
    "explore", "overview", "options", "ideas", "possibilities", "alternatives",
    "give me some", "list all", "what are my", "summarize everything",
}

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


def classify_intent(message: str) -> str:
    """Keyword fast-path → task | exploration | question. Zero cost."""
    msg = message.lower()
    task    = any(kw in msg for kw in _INTENT_TASK)
    explore = any(kw in msg for kw in _INTENT_EXPLORE)
    if task and not explore:
        return "task"
    if explore and not task:
        return "exploration"
    if task and explore:
        return "ambiguous"   # conflicting signals — let hybrid arbitrate
    return ""                # no signal — let hybrid arbitrate (defaults question)


async def classify_intent_hybrid(message: str, request_id: str = "") -> str:
    """Keyword first; only fall back to one cheap 8B call when keywords are
    silent or conflicting. Any failure → 'question'. Never raises."""
    kw = classify_intent(message)
    if kw in ("task", "exploration"):
        return kw

    # Ambiguous or no keyword signal → single constrained 8B classification.
    try:
        from llm import nim
        prompt = (
            "Classify the user's intent as exactly one word: task, exploration, "
            "or question.\n"
            "- task: wants you to perform/produce an action or artifact.\n"
            "- exploration: wants a broad survey of a topic or open-ended ideas.\n"
            "- question: wants a specific answer.\n"
            f"Message: {message}\nIntent:"
        )
        result = await nim.call(
            MODELS["llama"],
            [{"role": "user", "content": prompt}],
            request_id or "intent",
            model_params={"max_tokens": 4, "temperature": 0.0},
        )
        if result.get("ok") and result.get("content"):
            word = result["content"].strip().lower()
            for cand in ("task", "exploration", "question"):
                if cand in word:
                    return cand
    except Exception:
        logger.warning("[intent] hybrid classify failed rid=%s — defaulting question", request_id)
    return "question"


async def route(message: str, request_id: str) -> tuple[str, float]:
    start  = time.monotonic()
    choice = classify(message)
    model  = MODELS.get(choice, MODELS["llama"])
    latency_ms = (time.monotonic() - start) * 1000
    logger.info("[route] rid=%s model=%s latency_ms=%.2f", request_id, model, latency_ms)
    return model, latency_ms


def get_context_limit(model_name: str) -> int:
    return CONTEXT_WINDOWS.get(model_name, DEFAULT_CONTEXT_WINDOW)
