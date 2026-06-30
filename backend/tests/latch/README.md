# Connector-Intent Latch — Data Collection Harness

Tooling for the data-first tuning plan (`plans/connector-latch-data-plan.md`). Agents generate
labeled synthetic traffic; the latch logs scores; this harness joins them and prints the Phase 2
A/B/C measurements. **No tuning lives here** — it only describes the data.

## Pieces
- `agent_capture.py` — **API** wrapper the agents send through. One labeled capture row per send.
- `ui_capture.py` — **browser** twin (Playwright): drives the real UI at `localhost:3000`. Same
  capture schema → same `measure.py`. For UI-realism passes; for bulk volume use `agent_capture.py`.
- `prompt_bank.py` — band-tagged example prompts (weight toward none_intent / weak_real / tie).
- `measure.py` — joins capture labels with `latch_score` log lines → outputs A/B/C, can emit eval sets.

## Two drive paths (identical at the latch)
The connector latch is a pure server-side function of (message, query_emb), so API and UI produce the
**same** `latch_score` data. Pick by goal:
- **`agent_capture.py` (API)** — bulk latch-score volume. Fast, robust, precise labels. Default.
- **`ui_capture.py` (browser)** — full-stack realism (agent loop, confirm cards, OAuth-connected
  connectors as a user sees them). Needs `pip install playwright && playwright install chromium`
  (run from the host). `new_conversation()` = fresh COLD turn; consecutive `send()` = WARM.
```bash
python ui_capture.py --message "find my things" --band none_intent           # one cold send
python ui_capture.py --message "get that document" --band weak_real --connector drive --headed
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
```bash
# 1. collect (each agent, many sends; --connector required for positive/weak_real)
python agent_capture.py --message "find my things"    --band none_intent
python agent_capture.py --message "get that document" --band weak_real --connector drive
# multi-turn WARM session (shell): keep the conv id and continue it
CONV=$(python agent_capture.py --message "what's on my calendar" --band positive --connector calendar)
python agent_capture.py --message "ok thanks" --band easy_neg --conv "$CONV" --expect-warm

# 2. harvest the score lines the latch logged
(cd ../../../docker && docker compose logs api) | grep latch_score > scores.txt

# 3. measure (+ optionally emit the three eval sets next to the existing ones)
python measure.py --capture latch_capture.jsonl --scores scores.txt
python measure.py --capture latch_capture.jsonl --scores scores.txt --emit-evalsets ..
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
