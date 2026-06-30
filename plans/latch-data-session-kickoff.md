# Latch Data-Collection — Session Kickoff + Runbook

Two parts: **(A)** a paste-ready prompt to open the new session, **(B)** the operator runbook of exact
commands. Plan of record: `plans/connector-latch-data-plan.md`. Context feed:
`plans/solice-connector-latch-context.md`. Harness: `backend/tests/latch/`.

---

## Part A — paste this into the new session

> **Role.** You orchestrate a connector-intent latch **data-collection** run for JARVIS (NIM AI
> Gateway). You are NOT tuning thresholds — you generate labeled traffic, verify it logs, and hand
> back the measurement. The plan is `plans/connector-latch-data-plan.md` (Phase 0 shipped; we are
> doing Phase 2 collection). Do NOT set `INTENT_THRESHOLDS` / `FLOOR_THRESHOLD` / add a margin gate —
> that is a later, post-data step.
>
> **Graphify-first (mandatory).** `graphify-out/graph.json` exists. Never grep/read source for
> exploration without `graphify query "<q>"` first. Applies to every subagent you spawn — include
> this line in their prompts.
>
> **The system.** A per-turn latch scores the user message embedding vs per-connector centroids and
> logs one JSON line per non-cached turn (logger `connector_intent.scores`, `evt:"latch_score"`,
> in `backend/llm/service/stream.py:_resolve_connector_latches`). Connectors (Drive/Calendar/Gmail)
> are UI-exposed as of 2026-06-29. The latch only *flips* (`decision: latched_X`) when a connector is
> `active` (OAuth'd) for the sending user; scores log regardless.
>
> **Harness (`backend/tests/latch/`, both verified live):**
> - `agent_capture.py` — API path, bulk volume. Sends a labeled turn, writes one capture row.
> - `ui_capture.py` — Playwright path, drives the real UI at :3000 (realism / OAuth).
> - `measure.py` — joins capture rows + harvested `latch_score` lines → outputs A/B/C, emits eval sets.
> - `prompt_bank.py` — hard-band prompts. Weight traffic to none_intent / weak_real / tie.
>
> **Your sequence.**
> 1. Run the **go/no-go** (Runbook §2). Do not scale up until it is green.
> 2. Generate traffic per Runbook §3 — heavy on Bands 1–3, mixed cold/warm, varied phrasing.
> 3. Harvest + `measure.py` periodically; stop when each band has a few hundred rows across cold/warm.
> 4. Emit the eval sets (`--emit-evalsets`), report A/B/C, and STOP. Do not pick the fork — hand the
>    A/B/C numbers + eval sets back for the tuning decision.
>
> **Guardrails.** Use a throwaway user, not admin's real memory. Vary phrasing (identical text
> cache-hits and skips the latch). Respect rate limits (15 chat req/60s/user). Exclude `embed_fail`
> rows (measure.py already does). If over-fires are mostly WARM, flag it — that's a stickiness bug,
> not a threshold one; do not try to fix it by raising a threshold.
>
> **Done = ** eval sets written + A/B/C reported + a one-paragraph read of which fork the data points to
> (GAP / OVERLAP-cold / OVERLAP-warm), with the decision left to the human.

---

## Part B — operator runbook

All commands from `cd /home/scylla/dev/python-projects/ai-api/backend/tests/latch`.

### 1. Preconditions
- Stack up: `curl -s -o/dev/null -w '%{http_code}\n' localhost:8000/health` → 200; UI `localhost:3000` → 200.
- **Embedder healthy** — drive one send, confirm the latch line shows `"reason": "ok"` (not `embed_fail`).
- **One connector `active`** under the account the agents use. Connectors are OAuth'd under **admin**
  today; either drive flip-traffic as admin (`--user admin --pw admin-secret`) or OAuth a connector
  under a throwaway user first via `python ui_capture.py --headed` (do the Google consent in the
  window, then Integrations → connect Drive).

### 2. Go / no-go (do this before scaling)
```bash
# one API send (note the conv), then a couple via the connector-bearing account
python agent_capture.py --message "find my things" --band none_intent
python agent_capture.py --message "what files are in my drive" --band positive --connector drive --user admin --pw admin-secret
(cd ../../../docker && docker compose logs api --since 120s) | grep latch_score > scores.txt
PYTHONPATH=../.. python measure.py --capture latch_capture.jsonl --scores scores.txt
```
**Green if:** capture rows have real `conv_id`s, score lines parse, `reason: ok`, and `active:{drive:true}`
with at least one `decision: latched_drive` appears. If `decision` is always `none` → connector isn't
active for that user. If `reason: embed_fail` dominates → fix the embedder first.

### 3. Generate traffic (the run)
- **Bulk (API):** loop `agent_capture.py` over `prompt_bank.py`, weighted ~ none_intent 40% /
  weak_real 25% / tie 10% / positive 15% / easy_neg 10%. `--connector` is required for
  positive/weak_real. Spread non-flip score-band traffic across users to dodge the rate limit; keep
  flip traffic on the connector-bearing account and pace it (≤15/60s).
- **Cold vs warm (critical for output C):**
  - COLD = fresh conversation each send (API: omit `--conv`; UI: `new_conversation()`).
  - WARM = latch a connector on a clear turn, then send an *unrelated* later turn on the **same**
    `conv_id` (API: pass `--conv "$CONV" --expect-warm`; UI: consecutive `send()`). Script several
    of these — without them you can't tell fork OVERLAP-cold from OVERLAP-warm.
- **UI realism passes:** a smaller batch through `ui_capture.py` to exercise the full agent loop /
  confirm cards as a user sees them. Same capture file → same measurement.

### 4. Measure
```bash
(cd ../../../docker && docker compose logs api) | grep latch_score > scores.txt
PYTHONPATH=../.. python measure.py --capture latch_capture.jsonl --scores scores.txt
# when volume is sufficient, emit the three eval sets next to the existing ones:
PYTHONPATH=../.. python measure.py --capture latch_capture.jsonl --scores scores.txt --emit-evalsets ..
```
Read: **A** GAP→θ_min in the gap · OVERLAP→go to C. **B** δ sits above the none/tie margin cluster.
**C** over-fires COLD→θ_min+clarify · WARM→stickiness/TTL bug (different layer).

### 5. Do NOT
- Don't tune θ_min/δ or add the margin gate in this session — collect + measure only.
- Don't pollute admin's real memory — throwaway user.
- Don't reuse identical messages (cache-hit → no latch line).
- Don't raise a threshold to hide a WARM leak.
- Don't trust `embed_fail` rows (excluded by measure.py).
