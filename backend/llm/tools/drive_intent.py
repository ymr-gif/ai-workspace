"""Drive-intent latch signal (Q3 Task B).

Decides whether a turn shows genuine Google Drive intent, so the Drive tool
schemas can be withheld from the model until intent appears. Before the latch
flips, the Drive schema is absent from the prompt, so the model *cannot* call
`drive_list_files` — the "ehllo" cold case becomes structurally impossible, not
merely discouraged by `_DRIVE_RULES` prompt text (Task A, which did nothing alone).

The signal is an embedding cosine against a centroid DERIVED AT BOOT from a small
set of example Drive-intent phrases — NOT a keyword/regex match. The embedding
generalizes past the exact example words; the phrase list is the only place
example vocabulary lives, and the centroid is never hardcoded as a vector.

Embedder-specific: nv-embedqa-e5-v5 and bge-large-en-v1.5 share dimension (1024)
but NOT geometry — the same phrases embed to different points. The centroid
auto-regenerates at boot under either embedder, but DRIVE_INTENT_THRESHOLD is
tuned to e5's score distribution and will be wrong for bge. On a homeserver
bge swap, re-run tests/drive_intent_eval.jsonl and re-tune the threshold (see
backend/CLAUDE.md → LLM_BACKEND invariant).
"""

from __future__ import annotations

import asyncio
import logging
import math

from llm.embeddings import embed as embed_text

logger = logging.getLogger("drive_intent")

# Example Drive-intent sentences. The ONLY place example vocabulary lives. The
# centroid is the (normalized) mean of these embeddings, derived at boot — never
# a hardcoded vector. Structure is varied on purpose; do not cluster on one verb.
_DRIVE_INTENT_PHRASES = [
    "what files do I have in my drive",
    "show me the documents in my google drive",
    "open the document I have about the budget",
    "find a file in my drive",
    "search my google drive for a document",
    "list the files in my drive",
    "do I have a document about this in my files",
    "pull up a file from my drive",
    "look in my drive for a spreadsheet",
    "read one of my documents",
    "what is saved in my google drive",
    "find my file about the project",
    "open a folder in my drive",
    "get a document from my files",
    "which documents are in my drive",
    "check my google drive for a file",
    "retrieve a file from my documents",
    "where is my document saved in drive",
]

# Cosine threshold separating Drive-intent from non-Drive turns. TUNED against
# tests/drive_intent_eval.jsonl under the live embedder (nv-embedqa-e5-v5),
# 2026-06-28. The well-separated, wide-margin boundary is greetings/acks/chit-chat
# (scores ~0.29–0.39 — the actual over-fire bug) vs file requests; those can never
# latch here. Drive-intent vs *substantive task/coding* imperatives overlap
# intrinsically (single-centroid cosine ceiling), so this value is set
# precision-biased ("fail toward fewer tools; a wrong listing is worse than a
# missing one"): recall 14/20, specificity 18/20, overall 32/40. A weakly-phrased
# Drive ask that misses just needs a rephrase; "summarize"/"debug"-style turns are
# the only non-Drive leaks (Task A's _DRIVE_RULES then cover the post-latch call).
# Re-tune for bge on the homeserver port — see module docstring + backend/CLAUDE.md.
DRIVE_INTENT_THRESHOLD = 0.60

_centroid: list[float] | None = None
_centroid_lock = asyncio.Lock()


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def _embed_phrase(text: str, *, retries: int = 6) -> list[float] | None:
    # Sequential + retry: the NIM embedder rate-limits (429) a concurrent burst,
    # which would silently drop phrases and make the centroid non-deterministic —
    # and the tuned threshold assumes the FULL phrase set. One-time boot cost.
    for attempt in range(retries):
        v = await embed_text(text, input_type="query")
        if v:
            return v
        await asyncio.sleep(1.0 * (attempt + 1))
    return None


async def _build_centroid() -> list[float] | None:
    # input_type MUST match the query embed used at request time: helpers.py embeds
    # the user message as "query". The e5 embedder is ASYMMETRIC — query- and
    # passage-encoded text occupy different subspaces, so embedding these phrases as
    # "passage" would rank the cosine wrong while looking plausible. Keep "query".
    vecs = []
    for p in _DRIVE_INTENT_PHRASES:
        v = await _embed_phrase(p)
        if v:
            vecs.append(v)
    if len(vecs) < len(_DRIVE_INTENT_PHRASES):
        # Partial set → centroid drifts from the tuned threshold. Refuse rather than
        # ship a mistuned latch; the lazy path retries on the next request (self-heal).
        logger.warning("[drive_intent] centroid build incomplete (%d/%d phrases) — leaving unbuilt for retry",
                       len(vecs), len(_DRIVE_INTENT_PHRASES))
        return None
    dim = len(vecs[0])
    mean = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    centroid = _normalize(mean)
    logger.info("[drive_intent] centroid built from %d/%d phrases (dim=%d)", len(vecs), len(_DRIVE_INTENT_PHRASES), dim)
    return centroid


async def get_centroid() -> list[float] | None:
    """Boot-derived intent centroid, built once per process (lazy + locked).

    Returns None if the embedder was unreachable at build time; callers treat
    that as "no signal" (score 0.0 → not latched). The next call retries the
    build, so a transient embedder outage at first request self-heals.
    """
    global _centroid
    if _centroid is None:
        async with _centroid_lock:
            if _centroid is None:
                _centroid = await _build_centroid()
    return _centroid


async def warm_centroid() -> None:
    """Optional startup warm so the first Drive-active request doesn't pay the
    phrase-embedding cost. Safe to call from lifespan; failures are swallowed
    (the lazy path retries)."""
    try:
        await get_centroid()
    except Exception:
        logger.warning("[drive_intent] warm_centroid failed; will build lazily", exc_info=True)


async def drive_intent_score(query_emb) -> float:
    """Cosine of the query embedding against the boot-derived Drive-intent centroid.

    `query_emb` is None (no embed this turn) → 0.0, failing toward NOT latching
    (fewer tools). Centroid unbuildable (embedder down at boot) → 0.0 likewise.
    """
    if not query_emb:
        return 0.0
    centroid = await get_centroid()
    if not centroid:
        return 0.0
    q = _normalize(list(query_emb))
    return float(sum(a * b for a, b in zip(q, centroid)))
