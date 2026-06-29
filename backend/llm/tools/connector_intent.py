"""Per-connector intent latch signals (Q3 Task B + calendar/gmail generalization).

Generalizes the Drive intent latch to every capability-gated OAuth connector
(drive, calendar, gmail). Each connector's tool schemas are withheld from the
model until genuine intent for THAT connector appears in the session — an
embedding cosine of the turn's `query_emb` against a per-connector centroid
derived at boot from example phrases. Fixes the capability-only over-fire where
the tool-eager 70B called connector tools on greetings/chit-chat (e.g.
`drive_list_files` / `calendar_list_events` / `calendar_search_events {"query":"hi"}`).

NOT a keyword match — the cosine generalizes past the exact example words. The
phrase lists are example sentences for centroid derivation only.

Mechanism (resolved per turn in `llm/service/stream.py`): score the reused
`query_emb` vs `get_centroid(connector)`; `>= max(INTENT_THRESHOLDS[connector], FLOOR_THRESHOLD)` →
latch (Redis `{connector}_latched:{conv_id}`, latch-then-serve same turn, sticky
1h). The gate for each connector is `ctx.{connector}_active AND ctx.{connector}_latched`.

Embedder-specific: centroids auto-regenerate at boot under any embedder, but the
THRESHOLDS are tuned to nv-embedqa-e5-v5's score geometry and will be WRONG for
bge-large-en-v1.5 (same 1024-d, different geometry). On the homeserver swap,
re-run the `tests/{connector}_intent_eval.jsonl` sets and re-tune. See
backend/CLAUDE.md → LLM_BACKEND invariant.

Cross-connector talk: connector requests share a "check my X / find my Y" possessive
structure, so e.g. a gmail request scores high on the drive & calendar centroids too
(measured: gmail turns latch drive 13/20 @0.60). To stop one request latching multiple
connectors, the latch flip in `generate_stream` is **single-winner** — among active,
not-yet-latched connectors it latches only the top-scoring one (the correct connector
is the argmax ~always: gmail turns score gmail ~0.75 vs drive/cal ~0.60). This shrinks a
cross-talk/task-imperative false latch from all connectors to one.

Known ceiling (per connector): a single-centroid cosine separates greetings/chit-chat
cleanly from connector requests, but connector-vs-connector-vs-task-imperative bands
overlap — thresholds are precision-biased ("fail toward fewer tools"). The global
`FLOOR_THRESHOLD` (0.65) rejects weak winners that only "won" because every connector
scored low — a confident wrong latch is worse than a humble abstention. The latch is
sticky 1h, so a false latch poisons that one connector for the session until TTL. See
BUGS.md residual.
"""

from __future__ import annotations

import asyncio
import logging
import math

from llm.embeddings import embed as embed_text

logger = logging.getLogger("connector_intent")

# Example intent sentences per connector — the ONLY place example vocabulary lives.
# Centroid = normalized mean of these embeddings, derived at boot, never hardcoded.
# Each anchored on the connector's nouns (files/drive · schedule/calendar/events ·
# email/inbox/messages); structure varied to avoid clustering on one verb.
INTENT_PHRASES: dict[str, list[str]] = {
    "drive": [
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
    ],
    "calendar": [
        "what is on my calendar today",
        "do I have any meetings this week",
        "show me my schedule",
        "when is my next appointment",
        "add an event to my calendar",
        "schedule a meeting for tomorrow",
        "what events do I have on friday",
        "am I free this afternoon",
        "put a reminder on my calendar",
        "check my calendar for next monday",
        "do I have anything booked tomorrow",
        "create a calendar event for the call",
        "what is my agenda for today",
        "move my three pm meeting",
        "cancel the event on thursday",
        "list my upcoming events",
        "when am I meeting with the team",
        "block off time on my calendar",
    ],
    "gmail": [
        "check my email",
        "do I have any new messages",
        "show me my latest emails",
        "search my inbox for the invoice",
        "did I get an email from john",
        "what is in my inbox",
        "read my most recent email",
        "find the email about the meeting",
        "do I have any unread messages",
        "look up that email from support",
        "what emails did I get today",
        "show me messages from my boss",
        "find emails about the project",
        "open the email with the receipt",
        "check for new mail",
        "did anyone email me about the order",
        "search my gmail for the contract",
        "read the email from the bank",
    ],
}

# Cosine thresholds separating connector-intent from non-intent turns. TUNED against
# tests/{connector}_intent_eval.jsonl under the live embedder (nv-embedqa-e5-v5),
# 2026-06-28, precision-biased. Re-tune for bge — see module docstring + backend/CLAUDE.md.
INTENT_THRESHOLDS: dict[str, float] = {
    "drive": 0.60,     # recall 14/20, spec 18/20 (precision-biased)
    "calendar": 0.60,  # recall 18/20, spec 16/20
    "gmail": 0.65,     # recall 20/20, spec 19/20 (gmail separates cleanly)
}

# Global floor: a connector must clear BOTH its per-connector threshold AND
# this floor to latch. Prevents latching on a weak winner that only "won"
# because every connector scored low — a confident wrong latch is worse than
# a humble abstention. Already-latched connectors (sticky TTL) unaffected.
FLOOR_THRESHOLD = 0.65

_centroids: dict[str, list[float] | None] = {}
_locks: dict[str, asyncio.Lock] = {c: asyncio.Lock() for c in INTENT_PHRASES}


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


async def _build_centroid(connector: str) -> list[float] | None:
    # input_type MUST match the query embed used at request time: helpers.py embeds
    # the user message as "query". The e5 embedder is ASYMMETRIC — query- and
    # passage-encoded text occupy different subspaces. Keep "query".
    phrases = INTENT_PHRASES[connector]
    vecs = []
    for p in phrases:
        v = await _embed_phrase(p)
        if v:
            vecs.append(v)
    if len(vecs) < len(phrases):
        # Partial set → centroid drifts from the tuned threshold. Refuse rather than
        # ship a mistuned latch; the lazy path retries on the next call (self-heal).
        logger.warning("[connector_intent] %s centroid incomplete (%d/%d) — leaving unbuilt for retry",
                       connector, len(vecs), len(phrases))
        return None
    dim = len(vecs[0])
    mean = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    centroid = _normalize(mean)
    logger.info("[connector_intent] %s centroid built from %d/%d phrases (dim=%d)",
                connector, len(vecs), len(phrases), dim)
    return centroid


async def get_centroid(connector: str) -> list[float] | None:
    """Boot-derived intent centroid for `connector`, built once per process (lazy + locked).

    Returns None if the embedder was unreachable at build time; callers treat that
    as "no signal" (score 0.0 → not latched). The next call retries the build, so a
    transient embedder outage at first request self-heals.
    """
    if _centroids.get(connector) is None:
        async with _locks[connector]:
            if _centroids.get(connector) is None:
                _centroids[connector] = await _build_centroid(connector)
    return _centroids.get(connector)


async def warm_centroids() -> None:
    """Optional startup warm of all connector centroids so the first connector-active
    request doesn't pay the phrase-embedding cost. Safe to fire-and-forget from
    lifespan; failures are swallowed (the lazy path retries)."""
    for connector in INTENT_PHRASES:
        try:
            await get_centroid(connector)
        except Exception:
            logger.warning("[connector_intent] warm %s failed; will build lazily", connector, exc_info=True)


async def intent_score(connector: str, query_emb) -> float:
    """Cosine of the query embedding against `connector`'s boot-derived intent centroid.

    `query_emb` is None (no embed this turn) → 0.0, failing toward NOT latching
    (fewer tools). Centroid unbuildable (embedder down at boot) → 0.0 likewise.
    """
    if not query_emb:
        logger.debug("[intent_score] %s query_emb=%s → 0.0", connector, type(query_emb).__name__ if query_emb is not None else "None")
        return 0.0
    centroid = await get_centroid(connector)
    if not centroid:
        return 0.0
    q = _normalize(list(query_emb))
    return float(sum(a * b for a, b in zip(q, centroid)))
