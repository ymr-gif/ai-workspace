import logging
import time

import config

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

# Ack / closing lexicon (C2). A message qualifies as a pure closing turn only if
# EVERY token is in this set (plus: no '?', no digits, ≤6 tokens). It is a
# work-skipping optimization ONLY — a message that misses it falls through to the
# classifier, which owns the real decision, so incompleteness stays harmless.
# "thanks, but the formula is wrong" must NOT qualify (has out-of-set tokens).
_ACK_TOKENS = {
    "ok", "okay", "thanks", "thankyou", "thank", "you", "thats", "that's",
    "all", "got", "it", "cool", "nice", "bye", "goodbye", "great", "perfect",
    "sure", "yep", "man", "good", "day",
}


def _is_ack(message: str) -> bool:
    """Pure closing/acknowledgment turn — short-circuit, no LLM call. Qualifies
    only when every token is in _ACK_TOKENS, there is no '?', no digit, ≤6 tokens.
    Anything it misses falls through to the classifier (must stay harmless)."""
    msg = message.strip().lower()
    if not msg or "?" in msg or any(ch.isdigit() for ch in msg):
        return False
    tokens = [t.strip(".,!") for t in msg.split()]
    tokens = [t for t in tokens if t]
    if not tokens or len(tokens) > 6:
        return False
    return all(t in _ACK_TOKENS for t in tokens)


# Contrast/continuation markers that flip a "thanks…" opener into a real follow-up request
# ("thanks, BUT the formula is wrong", "though i have ANOTHER question"). Whole-token match.
# Deliberately NARROW + high-precision: only markers that ~never appear in a pure ack. Excludes
# now / more / one / next / and / also / though — those live in real closings ("all set now",
# "no more questions", "thanks though"), so vetoing on them would kill genuine acks (measured
# against tests/closing_intent_eval.jsonl). Ambiguous follow-ups are caught by the task-verb /
# '?' / digit checks instead, or simply score below CLOSING_THRESHOLD.
_REQUEST_MARKERS = {
    "but", "however", "actually", "wait", "instead", "except", "another",
}


def _looks_like_request(message: str) -> bool:
    """Shared closing veto — spans the cascade tiers, protects the semantic (cosine) tier from
    latching `closing` on a message that carries a real request. Returns True (→ NEVER closing)
    when the message has a '?', a digit, a URL, a contrast/continuation marker, or a task
    imperative verb (`_INTENT_TASK`). Precision backstop: fail toward NOT-closing."""
    msg = message.strip().lower()
    if not msg:
        return False
    if "?" in msg or any(ch.isdigit() for ch in msg) or "http" in msg:
        return True
    if any(kw in msg for kw in _INTENT_TASK):
        return True
    tokens = {t.strip(".,!:;") for t in msg.split()}
    return bool(tokens & _REQUEST_MARKERS)

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
    """Keyword fast-path → closing | task | exploration | question. Zero cost.

    `closing` (pure thanks/goodbye/ack) is checked FIRST via the ack lexicon so a
    goodbye never gets forced onto the task-intent branch (which pulls in the
    reasoning model + RAG and re-answers the prior question, unsolicited)."""
    if _is_ack(message):
        return "closing"
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
    silent or conflicting. Any failure → 'question'. Never raises.

    Returns closing | task | exploration | question. The ack lexicon short-circuits
    pure closing turns without the LLM call; anything it misses still reaches the 8B
    prompt (which also carries the `closing` label + few-shots)."""
    kw = classify_intent(message)
    if kw in ("closing", "task", "exploration"):
        return kw

    # Ambiguous or no keyword signal → single constrained 8B classification.
    try:
        from llm import nim
        prompt = (
            "Classify the user's intent as exactly one word: task, exploration, "
            "question, or closing.\n"
            "- task: wants you to perform/produce an action or artifact.\n"
            "- exploration: wants a broad survey of a topic or open-ended ideas.\n"
            "- question: wants a specific answer.\n"
            "- closing: only thanks / goodbye / acknowledgment, no new request.\n"
            "Examples:\n"
            "Message: okay thankyou, thats all\nIntent: closing\n"
            "Message: thanks, that's perfect\nIntent: closing\n"
            "Message: got it, cheers\nIntent: closing\n"
            "Message: thanks, but the formula is wrong\nIntent: task\n"
            "Message: ok how about arrays?\nIntent: question\n"
            f"Message: {message}\nIntent:"
        )
        result = await nim.call(
            config.MODELS["llama"],
            [{"role": "user", "content": prompt}],
            request_id or "intent",
            model_params={"max_tokens": 4, "temperature": 0.0},
        )
        if result.get("ok") and result.get("content"):
            word = result["content"].strip().lower()
            for cand in ("task", "exploration", "closing", "question"):
                if cand in word:
                    return cand
    except Exception:
        logger.warning("[intent] hybrid classify failed rid=%s — defaulting question", request_id)
    return "question"


async def route(message: str, request_id: str) -> tuple[str, float]:
    start  = time.monotonic()
    choice = classify(message)
    model  = config.MODELS.get(choice, config.MODELS["llama"])
    latency_ms = (time.monotonic() - start) * 1000
    logger.info("[route] rid=%s model=%s latency_ms=%.2f", request_id, model, latency_ms)
    return model, latency_ms


def get_context_limit(model_name: str) -> int:
    return config.CONTEXT_WINDOWS.get(model_name, config.DEFAULT_CONTEXT_WINDOW)
