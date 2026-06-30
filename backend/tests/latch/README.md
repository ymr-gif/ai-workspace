# Connector-Intent Latch — Data Collection Harness

Tooling for the data-first tuning plan (`plans/connector-latch-data-plan.md`). Agents generate
labeled synthetic traffic; the latch logs scores; this harness joins them and prints the Phase 2
A/B/C measurements. **No tuning lives here** — it only describes the data.

## START HERE — cold-start runbook (read first, do in order)

**Goal:** generate *labeled* traffic through the connector-intent latch, confirm it logs, then report
the A/B/C measurement + emit eval sets. You are **collecting data, NOT tuning the latch.**

**Run every command below from THIS directory** (`backend/tests/latch`) using **`python3`** — the
relative paths and `PYTHONPATH=../..` assume it. Graphify-first if you read code (`graphify query`).

**Hard rules**
1. Do NOT tune `INTENT_THRESHOLDS` / `FLOOR_THRESHOLD` or add a margin gate. Collect + measure only;
   the fork decision is human-gated — hand the numbers back.
2. Connectors are OAuth'd under **`admin`** (not `user`). Anything that must actually latch uses
   `--user admin --pw admin-secret`, else `decision` stays `none`. Score-band traffic can use any user.
3. Use the seeded throwaway accounts (`admin`/`admin-secret`, `user`/`user-secret`) — never real data.

**0. Prereqs — stack must be running**
```bash
curl -s -o /dev/null -w 'api %{http_code}\n' localhost:8000/health    # want 200
```
Not 200? → `(cd ../../../docker && docker compose up -d)`, wait ~20s, recheck.

**1. Go/no-go — confirm a real flip + a healthy embedder (before scaling)**
```bash
python3 agent_capture.py --message "what files do I have in my google drive" \
  --band positive --connector drive --user admin --pw admin-secret --capture gng.jsonl
(cd ../../../docker && docker compose logs api --since 120s) | grep latch_score | tail -1
```
GREEN = a line with `"reason": "ok"` AND `"decision": "latched_drive"`.
`reason: embed_fail` → embedder outage, pause. `decision: none` → wrong account / connector inactive.
(`gng.jsonl` is throwaway — go/no-go only reads the log line.)

**2. Collect — one command**
```bash
# fixed size:
python3 fleet.py --capture run.jsonl --admin-target 150 --score-target 400
# or run for hours (admin worker uses sessions → cold + lots of warm; score worker = cold volume):
python3 fleet.py --capture run.jsonl --duration 3h
```
Two seeded accounts ⇒ 2 workers (admin = mixed/sessions for flips+warm, user = score volume).
Throughput is bounded by per-send latency (~5–7s healthy), so ~8–10/min/worker → a 3h run ≈ ~1500–1800
rows/worker. Wider: seed more users (`../../create_user.py`) and pass `--accounts u1:pw,u2:pw,...`.
Watch the logs for `embed_fail` creeping in — if it dominates, the embedder relapsed; pause.

**Long runs & token budget (important):** two separate meters.
- *NIM tokens* (the traffic): **lean mode is ON by default** — each send caps the reply to 1 token, so
  the tool loop (the real token sink) never starts and the cache is bypassed (latch always logs). Add
  `--lean-model meta/llama-3.1-8b-instruct` to pin the cheapest model and dodge fallback churn. A
  multi-hour 2-worker run is single-digit dollars. (If NIM degrades, sends just get *slow* — tokens
  stay capped, you simply collect less.)
- *Claude tokens* (your agent tester): keep it **launch-and-poll**. Let `fleet.py`/`run_collection.py`
  generate the messages (zero LLM cost) and have your agent check back periodically. Do NOT have an
  LLM reason out every message for hours — that's the only thing that explodes. Reserve the
  `fleet.py --briefings` LLM-agent path for a short diversity burst, not the long haul.

**3. Measure + report**
```bash
(cd ../../../docker && docker compose logs api) | grep latch_score > scores.txt
PYTHONPATH=../.. python3 measure.py --capture run.jsonl --scores scores.txt --emit-evalsets ..
```
**Report back:** the `by reason` split, A (GAP/OVERLAP), B (margin cluster), C (cold/warm over-fires),
which eval sets were written, and a one-line read of the fork the data points to. **Do NOT pick or
apply the fork — that is the human's call.**

**Full briefing:** `plans/latch-data-session-kickoff.md` (role, weighting, cold/warm, don'ts).

## Pieces
- `agent_capture.py` — **API** wrapper the agents send through. One labeled capture row per send.
- `ui_capture.py` — **browser** twin (Playwright): drives the real UI at `localhost:3000`. Same
  capture schema → same `measure.py`. For UI-realism passes; for bulk volume use `agent_capture.py`.
- `prompt_bank.py` — band-tagged example prompts (weight toward none_intent / weak_real / tie).
- `run_collection.py` — **Layer 1**: one paced orchestrator. `--mode singles|sessions|mixed`
  (sessions = multi-turn continuous chats → the efficient WARM-row source), `--duration 3h` or
  `--target N`, weighted bands, templated phrasing, lean-by-default. One command = a whole run.
- `fleet.py` — **Layer 2**: spawns several Layer-1 workers in parallel (one per account; admin =
  flips+warm, others = score-band), all → one capture file. `--briefings` prints paste-ready prompts
  for human-launched LLM agents instead.
- `measure.py` — joins capture labels with `latch_score` log lines → outputs A/B/C, can emit eval sets.

## Two drive paths (identical at the latch)
The connector latch is a pure server-side function of (message, query_emb), so API and UI produce the
**same** `latch_score` data. Pick by goal:
- **`agent_capture.py` (API)** — bulk latch-score volume. Fast, robust, precise labels. Default.
- **`ui_capture.py` (browser)** — full-stack realism (agent loop, confirm cards, OAuth-connected
  connectors as a user sees them). Needs `pip install playwright && playwright install chromium`
  (run from the host). `new_conversation()` = fresh COLD turn; consecutive `send()` = WARM.
```bash
python3 ui_capture.py --message "find my things" --band none_intent           # one cold send
python3 ui_capture.py --message "get that document" --band weak_real --connector drive --headed
```

## How the join works
- The label must NOT go in the message text (it would be embedded into `query_emb` and shift every
  score). Join key is **(conv_id, order)**, captured out-of-band.
- `agent_capture.py` reads `conversation_id` from the `done` SSE event and writes a row per send
  with a per-conv `ordinal`.
- The latch emits one `latch_score` line per non-cached turn (logger `connector_intent.scores`,
  `backend/llm/service/stream.py:_resolve_connector_latches`).
- `measure.py` groups both by `conv_id`, sorts score lines by `turn`, and zips with the
  latch-expected capture rows by `ordinal`. Cache-hit sends are marked `latch_expected=False` so the
  alignment holds.

## Run

**Scaled collection (recommended) — one command:**
```bash
# Layer 2 fleet: admin worker (flips+warm) + score workers, all → run.jsonl
python3 fleet.py --capture run.jsonl --admin-target 150 --score-target 400
# or a single Layer 1 worker:
python3 run_collection.py --target 300 --user admin --pw admin-secret --capture run.jsonl
# then harvest + measure + emit eval sets:
(cd ../../../docker && docker compose logs api) | grep latch_score > scores.txt
PYTHONPATH=../.. python3 measure.py --capture run.jsonl --scores scores.txt --emit-evalsets ..
```

**Manual single sends (debugging / go-no-go):**
```bash
python3 agent_capture.py --message "find my things"    --band none_intent
python3 agent_capture.py --message "get that document" --band weak_real --connector drive --user admin --pw admin-secret
# multi-turn WARM session: keep the conv id and continue it
CONV=$(python3 agent_capture.py --message "what's on my calendar" --band positive --connector calendar --user admin --pw admin-secret)
python3 agent_capture.py --message "ok thanks" --band easy_neg --conv "$CONV" --expect-warm --user admin --pw admin-secret
```
`measure.py` imports the live `INTENT_THRESHOLDS`/`FLOOR_THRESHOLD` when run with the backend on the
path (run from `backend/`, or set `PYTHONPATH=backend`); otherwise it falls back to documented
defaults and says so.

## Outputs
- **A** — `max(none_intent argmax)` vs `min(weak_real target)` → GAP (θ_min lives in it) or OVERLAP.
- **B** — margin distribution on none_intent + tie → δ sits above this cluster.
- **C** — cold/warm split of over-fires → COLD ⇒ θ_min + clarify fixes it; WARM ⇒ the leak is
  stickiness/TTL, fix that layer, do **not** raise θ_min to mask it.

## Collection caveats (read before the run)
- **Connector must be `active`** under the agents' user, or `decision` stays `none` (scores still log
  → score bands usable, but no real flips / warm-leak data).
- **Embedder must be up.** Failed embeds log `reason: embed_fail`, scores 0.0 — `measure.py` excludes
  non-`ok` rows from the score histograms (reported separately). A flaky embedder = thin dataset.
- **Cache hits skip the latch** (no line). Vary phrasing — you want the spread anyway.
- **Rate limit**: 15 chat req/60s per user (reasoning model 5/60s). Spread score-band agents across
  users; keep flip/warm agents on the connected account and pace them.
- **Pollution**: agent traffic primes the 70B + memory pipeline. Use a throwaway user, not real data.
- **Volume**: aim for a few hundred rows per band across cold/warm for stable histograms, not tens.
