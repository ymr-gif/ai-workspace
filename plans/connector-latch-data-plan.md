# Connector-Intent Latch — Data-First Tuning Plan

> Companion to `solice-connector-latch-context.md` (the system context feed). This is the
> **execution plan**. Decision: **build the data, run one measurement, then ship floor + margin +
> the cold/warm split as one change.** Do not tune anything until the data exists.
>
> Status: **Phase 0 shipped 2026-06-29** (score logging live + connectors re-enabled). Phases 1–8 pending.

---

## Phase 0 — Instrument ✅ SHIPPED 2026-06-29

Add score logging. You can't tune blind, and the data doesn't exist yet.

Per turn, in `_resolve_connector_latches` (`backend/llm/service/stream.py`):

```
conv_id, turn, query_emb_present (bool + reason: rag_skip | embed_fail | ok),
scores {drive, calendar, gmail}, prior_latch_state (which connectors warm),
argmax, runner_up, margin, decision (latched_what / none), why
```

Two things this captures that you were blind to:
- **embed_fail vs rag_skip** — the `None` path blends these. Separated, or you chase ghost under-fires.
- **cold vs warm** — `prior_latch_state` tells you if an over-fire happened with a latch already on.
  This decides which layer you're even fixing.

**What shipped:**
- Logger `connector_intent.scores`, one JSON line/turn, `evt: "latch_score"`. Grep:
  `grep '"evt": "latch_score"'` the api logs.
- All 3 connectors scored every turn (cross-talk visibility); the flip still only considers
  active+unlatched (behavior unchanged).
- Fields: `conv_id, turn, query_emb_present, reason(ok|embed_fail|rag_skip), scores{drive,calendar,gmail},
  prior_latch_state, active, argmax/argmax_score, runner_up/runner_up_score, margin, decision, why, msg`.
- Connectors re-enabled in `frontend/src/hooks/useIntegrations.js`
  (`ENABLED_CONNECTOR_TYPES = ['google_drive','google_calendar','gmail']`) so admin OAuths in and
  real traffic flows through the latch.
- **Caveats for the dataset:** cache-hit turns return before the latch → no log line. While the NIM
  embedder is flaky, some turns log `reason: embed_fail` (that's signal, not lost data). `decision`
  stays `none` until a connector is `active` (admin must OAuth in).

Run 3–7 days. Collect real traffic. **No tuning yet.**

---

## Phase 1 — Build the missing eval data

Current sets (20 pos + 20 easy-neg ×3, `tests/{drive,calendar,gmail}_intent_eval.jsonl`) can't tune
θ_min. Easy negatives score near-zero; the over-fire never came from "hello." Build from real logs,
not synthesis:

```
none_intent_eval.jsonl    ← pull real over-fires from tool_call_logs (Band 1)
                             connector-adjacent, no real intent
                             "find my things", "check my stuff", "look that up"
weak_real_eval.jsonl      ← pull real correct terse fires (Band 3)
                             "get that document", "search for it"
tie_eval.jsonl            ← hand-write (~10, rare in wild) (Band 2)
                             "what's in my files and my email"
```

Tag every line `cold` or `warm` (from `prior_latch_state` in logs). This tag drives the whole
decision below.

---

## Phase 2 — One measurement, three outputs

Score every eval line against all 3 centroids. Produce:

```
A. max(none_intent score)  vs  min(weak_real score)
   → gap     = θ_min lives in the gap, clean
   → overlap = query_emb alone insufficient (go to Phase 4 fork)

B. margin distribution on cross-talk + tie sets
   → δ lives between correct-hit margins and tie margins

C. cold/warm split of the over-fires
   → mostly cold → θ_min + clarify fixes it
   → mostly warm → leak is stickiness/TTL, NOT the floor (different bug)
```

Don't guess `MARGIN_DELTA=0.10` or any θ_min. Both fall out of A and B histograms. The 0.05/0.20
bounds are sanity rails only.

---

## Phase 3 — The gate logic (ship once, both constants together)

```
latch winner IFF:
    score[winner] ≥ θ_min                        ← absolute floor (intent exists)
  AND
    score[winner] − score[runner_up] ≥ δ         ← margin (winner clear)

query_emb is None (any reason) → latch nothing
already-warm connectors        → unchanged, sticky TTL, floor/margin apply only to NEW flips
single active candidate        → margin auto-passes BUT still must clear θ_min
```

**Fix to the edge table:** single-candidate does **not** bypass the floor. That row was a hole — most
turns have one dominant connector, so skipping the floor there reopens over-fire.

> Current code is single-winner + floor only — **no δ/margin gate yet**. Phase 3 adds the margin term.

---

## Phase 4 — Fork on the data (decided in advance)

No re-deliberation. The measurement picks the branch:

```
A shows GAP:
    set θ_min in gap, set δ from margins, ship Phase 3. Done.

A shows OVERLAP + C says over-fires mostly COLD:
    set θ_min conservative (favor reject). Accept that some cold-vague
    requests don't latch → model asks "which document?" → user clarifies
    → next turn scores clean. Ship Phase 3.
    Rationale: under-fire on a cold vague turn is a clarifying question,
    not a bug. Over-fire is the bug. Trade the cheap loss for the real fix.

A shows OVERLAP + C says over-fires mostly WARM:
    STOP. θ_min won't help. The leak is stickiness — a connector latched
    on a clear turn, then stayed warm and fired on an unrelated later turn.
    Fix TTL / add a per-turn re-score / decay instead. Different layer.
    Do NOT raise θ_min to mask a stickiness bug.

A shows OVERLAP + cold-vague-real is COMMON (rare case):
    only here: add context signal (blend last-N-turn embedding, or last
    latched connector as prior). Parked work. Last resort. Don't pre-build it.
```

---

## Factors that affect this — own them

```
- Embedder geometry: tuned on e5-v5. On bge-large migration, θ_min and δ
  MUST re-tune. Same dim, different geometry. Don't port the numbers.
- input_type asymmetry: centroid phrases must use input_type="query" to
  match query_emb. A mismatch silently shifts every score. Verify before
  trusting any histogram.
- Centroid drift: intent meanings drift as you add phrases. Re-measure
  θ_min/δ when you touch centroids. Log centroid version with scores.
- Single-winner vs multi-connector: current logic flips ONE. "Email me the
  file from Drive" needs two. After floor/margin land, test multi-connector
  union. If broken, decide defer vs fix THEN — not now. Stickiness covers
  many multi cases across turns already.
- Conservative θ_min over-corrects: too high swaps over-fire for under-fire.
  You spent effort killing over-fire; don't trade it for silent under-fire.
  Tune LOW, raise only if logs show residual over-fire.
- Clarify-fallback depends on the model actually asking: if A (abstention
  rules) doesn't prompt a clarifying question on no-tool-vague input, the
  cold-vague case dead-ends in silence. Verify A produces "which X?"
  behavior, or the fork-B fallback doesn't actually recover.
```

---

## Sequence, flat

```
1. Ship score logging (cold/warm, embed_fail/rag_skip)      ← ✅ DONE 2026-06-29
2. Collect 3–7 days
3. Build none + weak_real + tie eval sets from real logs
4. Run measurement → outputs A, B, C
5. Branch per Phase 4 (pre-decided)
6. Ship θ_min + δ together, fix single-candidate floor hole
7. Re-tune on bge migration. Re-measure on centroid edits.
8. AFTER stable: test multi-connector union → decide defer/fix
```

---

## What NOT to do

- Don't set θ_min or δ now. No data. Guessing = the original sin.
- Don't wake the prefilter. Unrelated. 25 tools is fine for 70B.
- Don't add context-blend until logs prove cold-vague-real is common.
- Don't raise θ_min to hide a warm-leak. Fix the right layer.

Start at step 1 (done). Logging was the only thing correctly doable before the data exists.
Everything downstream waits on it.
