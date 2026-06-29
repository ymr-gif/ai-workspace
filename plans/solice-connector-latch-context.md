# SOLICE — Connector Intent Latch: Context Feed

> **Staleness pass applied 2026-06-29** against the live code
> (`backend/llm/tools/connector_intent.py`, `backend/llm/service/stream.py`,
> `BUGS.md:40,55`, `QUEUE.md:65`, `backend/CLAUDE.md`). Corrected sections are tagged
> **[UPDATED]**; superseded plan content is kept but re-labeled **[DEFERRED]** so the
> original intent survives for the bge/connector-re-enable milestone.

## What this system is
Solice = self-hosted memory-augmented AI assistant. FastAPI backend.
Connectors: Google Drive, Calendar, Gmail. Native integrations (not MCP).

**[UPDATED] Connector status:** all three connectors are **UI-stubbed** —
`ENABLED_CONNECTOR_TYPES = []` (frontend). No user can OAuth in, so **no active connector
rows exist and the latch never fires** — it is harmless dormant code today (`BUGS.md:40,55`).
Everything below describes the latch as built; it is live-relevant only once connectors are
re-enabled.

## The problem being solved
Capability-only gates over-fire. Old pattern:

    lambda ctx: ctx.drive_active   # checks "CAN I?" not "SHOULD I?"

→ connector tools fire when user didn't want them.
Pre-stub evidence (live, before connectors were stubbed): `calendar_search_events {"query":"hi"}`
in `tool_call_logs`. Class bug — same pattern in Drive, Calendar (`_cal_full_gate`,
`calendar_tools.py:23`), Gmail (`_gmail_full_gate`, `gmail_tools.py:21`). Drive gate is
`_drive_gate` (`drive_tools.py:59`).

## Two-layer defense (BOTH implemented)
- **B — Semantic latch** (code, hard gate): cosine(query_emb, per-connector centroid) vs
  threshold → exposes connector schemas or not. State in Redis:
  `{connector}_latched:{conv_id}`, `ex=3600`, sticky.
- **A — Abstention-bias rules** (prompt text, soft gate): keyword-free `_{connector}_RULES`
  nudge the model to hold back. Passive. Read by the model alongside schemas. Covers the
  post-latch trivial-turn window.

## Order of operations (verified)

    1. User message
    2. Build context (query_emb via embed_text(msg, input_type="query"), RAG, memory)
       [model selection — runs BEFORE latch]
       [DB+Redis connector flag read: _drive_active, _calendar_latched, …]
       [embed_status (ok|failed|skipped) recorded in the context dict]
    3. B — semantic latch: _resolve_connector_latches(actives, latched, conv_id, query_emb, embed_status)
       per-connector cosine vs centroid → single winner flips → Redis written
       [ToolContext built with latch results]
       [should_inject(ctx) reads latch from ctx]
    4. select_tool_schemas (prefilter — DORMANT, TOOL_PREFILTER_THRESHOLD=32, ~25 tools)
    5. build_context_messages — A rules injected at base_messages[1:1]
       schemas passed to call_stream as tools= (separate channel from messages)
    6. Model decides (call_stream)
    7. execute_tool → append → loop

RULE: B must run before step 4 (schema assembly). A is passive prompt context, not a runtime step.
A (messages) and schemas (tools= param) arrive at the model simultaneously at step 6, different channels.

**[UPDATED]** `_resolve_connector_latches` signature carries `embed_status` as a 5th arg
(`stream.py:32`). Resolution point is `backend/llm/service/stream.py:32`, NOT `registry.py`.

## Current latch mechanics
- Only the current `query_emb` is scored. NO history. `conv_id` used only for the Redis key
  (TTL stickiness).
- `intent_score()` — `connector_intent.py:204`; pure cosine on one normalized vector, return at
  `:217`.
- **[UPDATED] Single-winner argmax.** Among ACTIVE, not-yet-latched connectors, only the
  top-scoring one flips per turn — and only if it clears **both** its per-connector threshold
  **and** the global floor. Already-warm connectors unchanged (sticky TTL).

## Shipped gate logic **[UPDATED — replaces the original "floor AND margin (δ)" plan]**

The code does **not** implement a margin/δ gate. There is no `MARGIN_DELTA`, no `runner_up`
comparison. Cross-talk is handled by single-winner; weak winners by the floor.

    latch winner IFF:
        winner = argmax(scores over active & unlatched connectors)
        scores[winner] >= max(INTENT_THRESHOLDS[winner], FLOOR_THRESHOLD)
    query_emb is None (any reason) → all scores 0.0 → latch nothing
    already-warm connectors → unchanged, sticky TTL refresh; floor/threshold apply only to NEW flips
    single active candidate → still must clear max(per-connector, FLOOR)  (no margin auto-pass exists)

Shipped constants (`connector_intent.py`), tuned 2026-06-28/29 against the 40-line eval sets,
precision-biased:

    INTENT_THRESHOLDS = {"drive": 0.60, "calendar": 0.60, "gmail": 0.65}
    FLOOR_THRESHOLD   = 0.65

Floor rationale: rejects a winner that only "won" because every connector scored low — a confident
wrong latch is worse than a humble abstention. Example: "help me debug" ≈ 0.66 clears drive 0.60 but
NOT floor 0.65 → no latch (`BUGS.md:55`).

> **[UPDATED] Why this differs from the original plan.** The original feed said "do NOT set θ_min
> or δ now; ship logging first; collect real traffic." That was overtaken: thresholds + floor were
> shipped immediately, then connectors were UI-stubbed. Because the latch is now **inert** and the
> numbers are tuned to nv-embedqa-e5-v5 geometry (and **must** be re-tuned on the bge swap
> regardless), the shipped values stand as a precision-biased placeholder. The data-first plan below
> is preserved as the re-enablement checklist.

## **[DEFERRED]** Data-first tuning plan — execute on connector re-enable + bge swap

Park until `ENABLED_CONNECTOR_TYPES` exposes connectors AND the home-server bge-large-en-v1.5 swap is
done (`QUEUE.md:65`). None of these are shipped today; the latch produces no traffic while stubbed.

### Why it couldn't be tuned from existing evals
Existing evals: `backend/tests/{drive,calendar,gmail}_intent_eval.jsonl`, 40 lines each
(20 positive + 20 shared easy-negatives like "hello", "thanks", tech Qs). Easy negatives score ~0 —
trivial. Over-fire never came from "hello"; it came from connector-adjacent vagueness the eval sets
don't contain. Tuning the floor on easy negatives sets it too low.

### Execution sequence (deferred)

    1. SHIP structured score logging in _resolve_connector_latches. Per turn:
       conv_id, turn, query_emb_present (bool + reason: rag_skip|embed_fail|ok),
       scores{drive,calendar,gmail}, prior_latch_state (cold|warm per connector),
       argmax, runner_up, margin, decision, why.
       (Today only minimal logging exists: stream.py:64-79 — "all scores 0.0" and
        "winner below floor", plus embed_status. The full record is NOT shipped.)
    2. Collect 3–7 days real traffic. NO tuning.
    3. Build missing eval sets FROM REAL tool_call_logs (none exist today):
       none_intent_eval.jsonl   ← real over-fires (connector-adjacent, no intent)
       weak_real_eval.jsonl     ← real correct terse fires ("get that document")
       tie_eval.jsonl           ← hand-write ~10 ("files and my email")
       Tag every line cold|warm from prior_latch_state.
    4. Measure: max(none) vs min(weak_real) gap/overlap; margin distribution; cold/warm split.
    5. FORK (pre-decided):
       GAP                          → set floor in the gap; decide whether a margin/δ gate is
                                       worth adding (single-winner may already suffice). Ship.
       OVERLAP + over-fires COLD    → conservative floor (favor reject); cold-vague → clarify
                                       fallback. Ship.
       OVERLAP + over-fires WARM    → STOP. Leak is stickiness/TTL, not floor. Fix TTL /
                                       per-turn re-score / decay. Do NOT raise floor to mask it.
       OVERLAP + cold-vague-real COMMON → add context signal (blend last-N-turn emb, or
                                       last-latched-connector prior). LAST resort.
    6. Ship the re-tuned floor (+ optional margin gate); recheck the single-candidate path.
    7. AFTER stable: multi-connector union ("email me the file from Drive" needs Drive+Gmail).
       Decide defer vs fix THEN. Stickiness covers many multi cases across turns.

### Factors that affect correctness (own these)
- **Embedder geometry:** thresholds + floor tuned on nv-embedqa-e5-v5 (1024-d, NIM). On
  bge-large-en-v1.5 (homeserver) they are WRONG — same dim, DIFFERENT geometry. Centroids
  auto-regenerate at boot; the THRESHOLDS do not. Re-run the eval sets, re-set all three +
  the floor, recheck cross-talk. (`backend/CLAUDE.md` → LLM_BACKEND invariant; `QUEUE.md:65`.)
- **input_type asymmetry:** centroid phrases use `input_type="query"` to match `query_emb`
  (honored: `_build_centroid`/`_embed_phrase`, `connector_intent.py`). The e5 embedder is
  asymmetric; a mismatch silently shifts every score. Keep "query".
- **Centroid drift:** re-measure thresholds/floor whenever `INTENT_PHRASES` are edited; log a
  centroid version with scores.
- **embed_fail vs rag_skip:** both yield `query_emb=None` → fail toward NOT latching (safe). But
  `embed_fail` = silent connector death on a REAL request. `embed_status` (ok|failed|skipped)
  disambiguates — keep it in logs.
- **Conservative floor over-corrects:** too high swaps over-fire for under-fire. Tune low, raise
  only if logs show residual over-fire.
- **Clarify fallback depends on A** actually asking "which X?" on no-tool vague input. Verify A
  produces that behavior, else cold-vague dead-ends in silence.

## Known residuals (post-latch, while connectors were live — `BUGS.md:55`)
1. **Post-latch trivial turns** — once latched, "thanks"/"ok" can still fire the connector's tools
   (schema legitimately present; the `_RULES` prompt is the only guard, weak on the 70B).
2. **Sticky-latch session poisoning** — sticky 1h; a false latch on a substantive task/coding turn
   flips a connector on for the session. Single-winner caps the blast radius at ONE connector.
   Floor (0.65) mitigates. Decay/2-class/8B-prepass alternatives deferred.
3. **Verification rigor** — cold-case tests are structural/deterministic (firm); probabilistic 70B
   behavioral tests were run once, not the 3–5 repeats originally specced.

## Do NOT
- Do NOT re-tune the floor/thresholds before the bge swap — they will change anyway.
- Do NOT wake the prefilter. Unrelated. 25 tools fine for the 70B.
- Do NOT cut tool count to fix abstention. Over-fire ≠ tool-count strain.
- Do NOT add context-blend until logs prove cold-vague-real common.
- Do NOT raise the floor to hide a warm-leak. Fix the right layer (TTL/decay).
- Do NOT flip a connector to `needs_reauth` on a 403 — that hides the tool; return `_forbidden()`
  and stay `active` so the model relays the fix.

## Generalization target **[partly shipped / partly DEFERRED]**
Shipped: the latch already generalizes across drive/calendar/gmail via module-level
`INTENT_PHRASES`/`INTENT_THRESHOLDS` dicts + single-winner (`connector_intent.py`). One impl retires
the capability-only over-fire class across all three connectors.
Deferred: refactor into a `ConnectorIntentLatch` class (per-connector centroids/keys/thresholds as
config), multi-connector union, hysteresis (θ_on/θ_off), multi-centroid — once connectors are live.

## Stack
FastAPI, Redis, ARQ, pgvector, PostgreSQL, async SQLAlchemy 2.0/asyncpg.
NVIDIA NIM APIs (current) → llama.cpp homeserver (migration target).
Embedder: nv-embedqa-e5-v5 (NIM) / bge-large-en-v1.5 (homeserver).
Primary model: meta/llama-3.3-70b-instruct. Weak on abstention (the reason A+B exist).

## Current state / first action
**[UPDATED]** The latch is **shipped and inert** (connectors UI-stubbed). Nothing to ship now.
When connectors are re-enabled on the home-server/bge stack, the first action is **structured score
logging** (deferred step 1), then the data-first re-tune sequence above.
