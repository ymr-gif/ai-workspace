"""Semantic closing-intent signal (tier-2 of the closing-intent cascade).

A *closing* turn is pure thanks / goodbye / acknowledgment with no new request. Detecting it
lets `_build_stream_context` skip the embed's downstream (RAG + graph) and `generate_stream`
drop tools + route to llama-8B, so a goodbye isn't misrouted to the 120B + RAG and re-answered
unsolicited (the 2026-07-08 bug).

This module is the **semantic tier** of a 3-tier cascade (see `llm/router.py` `_is_ack` +
`classify_intent_hybrid`, and `api/chat/helpers.py`):

  tier 1  pre-embed lexicon `_is_ack` (allowlist)     — ≤~3-tok obvious acks, zero cost, zero FP
  tier 2  THIS module, post-embed nearest-example      — medium/paraphrased acks the lexicon misses
  tier 3  the 8B classifier (has a `closing` label)    — ambiguous / reach-the-8B turns

Mechanism mirrors `llm/tools/connector_intent.py`: `_CLOSING_PHRASES` → per-phrase normalized
embeddings (the "anchor set", built once at boot) → `closing_score(query_emb)` = the MAX cosine of
the turn's query embedding against any anchor (nearest-example, NOT a single mean — a mean punishes
short terse acks). NOT a keyword match; the cosine generalizes past the exact example words.

**Cost:** tier 2 rides the embedding RAG already computes for medium turns — it adds one cosine over
~24 anchors, no new embed call. Tier-1 acks and ≤2-word trivials skip the embed entirely, so tier 2
never runs on them (`query_emb is None` → score 0.0).

**Precision-biased:** every path fails toward NOT-closing. A false negative wastes a normal short
reply; a false positive drops tools + skips RAG on real work = the original bug in reverse. The
shared `_looks_like_request` veto (in `router.py`) gates this tier before the cosine is trusted, so
"thanks, but the formula is wrong" (scores high, starts with "thanks") can never latch closing.

**Embedder-specific:** the anchor set auto-regenerates at boot under any embedder, but
`CLOSING_THRESHOLD` + the token band are tuned to nv-embedqa-e5-v5's nearest-example score geometry
(which runs HOT) against `tests/closing_intent_eval.jsonl`. Re-run the eval + re-tune on the
bge-large-en-v1.5 swap — same obligation as the connector `INTENT_THRESHOLDS`. See
backend/CLAUDE.md → LLM_BACKEND invariant.
"""

from __future__ import annotations

import asyncio
import logging
import math

from llm.embeddings import embed as embed_text

logger = logging.getLogger("closing_intent")

# Example closing/ack sentences — the ONLY place example vocabulary lives. Varied so the anchor
# cloud isn't clustered on "thanks": plain acks, sign-offs, "I'm done/set", satisfied closings,
# and medium polite closings (the band tier-2 owns). The cosine generalizes to unseen phrasings.
_CLOSING_PHRASES: list[str] = [
    "thanks that's all",
    "okay thank you, that's everything",
    "great, thanks so much for the help",
    "perfect, that's all i needed",
    "appreciate it, i'm all set now",
    "thank you, no more questions",
    "got it, thanks a lot",
    "that's everything for now, thanks",
    "awesome, that works, thank you",
    "cool, i think i'm good now",
    "thanks, that answers my question",
    "alright, that's all from me",
    "thank you so much, have a good day",
    "no worries, i'm done here thanks",
    "that's exactly what i needed, cheers",
    "okay great, i'll take it from here thanks",
    "thanks for walking me through that",
    "that's all i wanted to know, thank you",
    "perfect, nothing else for now",
    "thanks, i really appreciate your help",
    "we're all good now, thank you",
    "that clears it up, thanks a bunch",
    "goodbye and thanks again",
    "that's it, thank you for everything",
]

# Nearest-example cosine threshold separating closing from non-closing turns. TUNED 2026-07-08
# against tests/closing_intent_eval.jsonl (40 turns) under the live embedder (nv-embedqa-e5-v5),
# at the tier-2 operating point (shared `_looks_like_request` veto + token band applied):
# thr=0.83 → recall 17/20 (0.85), specificity 20/20 (1.00, ZERO false positives). Precision-biased:
# a false positive drops tools + skips RAG on real work = the original misfire in reverse, so
# zero-FP wins over recall. The 3 missed acks fall through to the tier-3 8B classifier (which has
# a `closing` label). Two non-vetoed question-FPs ("can you explain that part again" 0.82,
# "thanks, and how do i format the cells" 0.80) sit just under 0.83 — that residual sets the floor.
# Nearest-example runs HOT; re-tune for bge — see module docstring + backend/CLAUDE.md.
CLOSING_THRESHOLD = 0.83

# Token band tier-2 is trusted in. Below _MIN the cosine is noisy (short utterances) → leave those
# to the lexicon / 8B; ≤2-word turns skip the embed anyway so they never reach here. Above _MAX a
# pure closing is unlikely and the veto handles trailing requests. Bounds set from D2 measurement.
_TIER2_MIN_TOKENS = 3
_TIER2_MAX_TOKENS = 18

_anchors: list[list[float]] | None = None
_lock = asyncio.Lock()


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def _embed_phrase(text: str, *, retries: int = 6) -> list[float] | None:
    # Sequential + retry: the NIM embedder rate-limits (429) a concurrent burst, which would
    # silently drop phrases and make the anchor set non-deterministic — the tuned threshold
    # assumes the FULL phrase set. One-time boot cost. input_type="query" MUST match the
    # request-time query embed (e5 is asymmetric — query/passage occupy different subspaces).
    for attempt in range(retries):
        v = await embed_text(text, input_type="query")
        if v:
            return v
        await asyncio.sleep(1.0 * (attempt + 1))
    return None


async def _build_anchors() -> list[list[float]] | None:
    vecs: list[list[float]] = []
    for p in _CLOSING_PHRASES:
        v = await _embed_phrase(p)
        if v:
            vecs.append(_normalize(list(v)))
    if len(vecs) < len(_CLOSING_PHRASES):
        # Partial set → the tuned threshold assumes the FULL set. Refuse rather than ship a
        # mistuned signal; the lazy path retries (self-heal on next call).
        logger.warning("[closing_intent] anchors incomplete (%d/%d) — leaving unbuilt for retry",
                       len(vecs), len(_CLOSING_PHRASES))
        return None
    logger.info("[closing_intent] anchors built from %d phrases (dim=%d)", len(vecs), len(vecs[0]))
    return vecs


async def get_anchors() -> list[list[float]] | None:
    """Boot-derived normalized phrase embeddings, built once per process (lazy + locked). None if
    the embedder was unreachable at build time → callers treat as "no signal" (score 0.0). The
    next call retries, so a transient outage self-heals."""
    global _anchors
    if _anchors is None:
        async with _lock:
            if _anchors is None:
                _anchors = await _build_anchors()
    return _anchors


async def warm_closing_anchors() -> None:
    """Optional startup warm of the anchor set so the first medium turn doesn't pay the
    phrase-embedding cost. Safe to fire-and-forget from lifespan; failures swallowed (lazy retry)."""
    try:
        await get_anchors()
    except Exception:
        logger.warning("[closing_intent] warm failed; will build lazily", exc_info=True)


async def closing_score(query_emb) -> float:
    """Nearest-example closing signal: the MAX cosine of the query embedding against any anchor.

    `query_emb` None/empty (no embed this turn) → 0.0, failing toward NOT-closing. Anchors
    unbuildable (embedder down at boot) → 0.0 likewise.
    """
    if not query_emb:
        return 0.0
    anchors = await get_anchors()
    if not anchors:
        return 0.0
    q = _normalize(list(query_emb))
    return max(float(sum(a * b for a, b in zip(q, anc))) for anc in anchors)
