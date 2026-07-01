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

Mechanism (resolved per turn in `llm/service/stream.py`): score the reused `query_emb` by
NEAREST-EXAMPLE — the MAX cosine over `get_anchors(connector)` (every phrase's embedding, not a
single mean); `>= max(INTENT_THRESHOLDS[connector], FLOOR_THRESHOLD)` → latch (Redis
`{connector}_latched:{conv_id}`, latch-then-serve same turn, sticky 1h). The gate for each
connector is `ctx.{connector}_active AND ctx.{connector}_latched`.

NOTE (2026-07-01): scoring changed from mean-centroid cosine to nearest-example MAX. Max runs
HIGHER than mean, so `INTENT_THRESHOLDS`/`FLOOR_THRESHOLD` below are the OLD mean-tuned values and
are now MISCALIBRATED — re-measure the weak_real/none_intent distributions and re-set them before
trusting live flips. (Motivation: terse genuine requests scored ~0.61 under the mean, overlapping
vague turns; nearest-example lets them match a terse anchor. See BUGS.md / RUNLOG.)

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
        # terse anchors — genuine short requests carry the connector noun (file/doc/spreadsheet)
        "open my document",
        "read that file",
        "grab the spreadsheet",
        "pull up my doc",
        "which file has this",
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
        # terse anchors — carry the connector noun (meeting/calendar/agenda/schedule)
        "when is my meeting",
        "what's my agenda",
        "put this on my calendar",
        "do I have anything scheduled",
        "any meetings on my calendar",
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
        # terse anchors — carry the connector noun (email/inbox/mail/message)
        "show my inbox",
        "did I get any email",
        "open my messages",
        "who emailed me",
        "look through my mail",
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
#
# Recalibrated 0.65→0.70 on 2026-07-01 for the nearest-example (max) scoring, which runs hotter
# than the old mean cosine. A/B on 150 weak_real + 150 none_intent: at 0.65 the new scoring
# over-fires 61% of vague turns; at 0.70 over-fire drops to ~15% (vs 37% for old@0.65) while genuine
# recall is ~28% — the rest is meant to be recovered by the clarify fallback (the bands overlap;
# no floor separates them). Provisional/precision-biased; the per-connector INTENT_THRESHOLDS above
# (0.60/0.60/0.65) are mean-tuned and now DOMINATED by this floor. Re-measure with more data.
FLOOR_THRESHOLD = 0.70

_anchors: dict[str, list[list[float]] | None] = {}
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


async def _build_anchors(connector: str) -> list[list[float]] | None:
    # NEAREST-EXAMPLE model: keep every phrase's normalized embedding, not a single mean.
    # A single mean-centroid punishes short/terse genuine requests ("read that file") — they
    # sit far from the average of long descriptive phrases and score low, overlapping vague
    # connector-adjacent turns. Scoring against the MAX over individual phrases lets a terse
    # request match a nearby example instead of the diluted average.
    # input_type MUST match the request-time query embed: helpers.py embeds the user message
    # as "query"; the e5 embedder is ASYMMETRIC (query/passage occupy different subspaces).
    phrases = INTENT_PHRASES[connector]
    vecs = []
    for p in phrases:
        v = await _embed_phrase(p)
        if v:
            vecs.append(_normalize(list(v)))
    if len(vecs) < len(phrases):
        # Partial set → the anchor cloud is incomplete and the tuned threshold assumes the
        # FULL set. Refuse rather than ship a mistuned latch; the lazy path retries (self-heal).
        logger.warning("[connector_intent] %s anchors incomplete (%d/%d) — leaving unbuilt for retry",
                       connector, len(vecs), len(phrases))
        return None
    logger.info("[connector_intent] %s anchors built from %d phrases (dim=%d)",
                connector, len(vecs), len(vecs[0]))
    return vecs


async def get_anchors(connector: str) -> list[list[float]] | None:
    """Boot-derived normalized phrase embeddings for `connector`, built once per process
    (lazy + locked). None if the embedder was unreachable at build time → callers treat as
    "no signal" (score 0.0). The next call retries, so a transient outage self-heals."""
    if _anchors.get(connector) is None:
        async with _locks[connector]:
            if _anchors.get(connector) is None:
                _anchors[connector] = await _build_anchors(connector)
    return _anchors.get(connector)


async def warm_centroids() -> None:
    """Optional startup warm of all connector anchor sets so the first connector-active
    request doesn't pay the phrase-embedding cost. Safe to fire-and-forget from lifespan;
    failures are swallowed (the lazy path retries). (Name kept for the lifespan import.)"""
    for connector in INTENT_PHRASES:
        try:
            await get_anchors(connector)
        except Exception:
            logger.warning("[connector_intent] warm %s failed; will build lazily", connector, exc_info=True)


async def intent_score(connector: str, query_emb) -> float:
    """Nearest-example intent signal: the MAX cosine of the query embedding against any of
    `connector`'s phrase embeddings.

    `query_emb` is None/empty (no embed this turn) → 0.0, failing toward NOT latching. Anchors
    unbuildable (embedder down at boot) → 0.0 likewise.
    """
    if not query_emb:
        logger.debug("[intent_score] %s query_emb=%s → 0.0", connector, type(query_emb).__name__ if query_emb is not None else "None")
        return 0.0
    anchors = await get_anchors(connector)
    if not anchors:
        return 0.0
    q = _normalize(list(query_emb))
    return max(float(sum(a * b for a, b in zip(q, anc))) for anc in anchors)
