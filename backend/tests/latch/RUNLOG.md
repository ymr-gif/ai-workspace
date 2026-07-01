# Latch Data Collection — Notes, Checklist & Run Log

Read this with the README. **Cold agent:** read the "Keep in account" notes, do the work, then
**append a dated entry to the Run log** below after every collection/measure run (rows, reason split,
A/B/C, anomalies). Tick boxes as they're done. Don't delete history — append.

---

## Keep in account (what this is / isn't)

- **Primary purpose = latch-tuning DATA.** Collect how messages score; do NOT tune θ_min/δ here.
  Collect → measure → report A/B/C → a human picks the fork. (See `plans/connector-latch-data-plan.md`.)
- **Byproduct = a pipeline soak.** Sustained traffic exercises auth, RAG/pgvector, Neo4j memory, the
  embedder, routing, model, and DB/Redis writes. Useful, but it's **paced & gentle — NOT a load/stress
  test.** Don't read throughput limits from it.
- **Lean mode (default) does NOT test connector tool execution.** `max_tokens=1` means the latch
  *decides* to expose Drive/Calendar/Gmail but the model never *calls* the tools → no Google API
  round-trips. You're testing the **gating decision**, not the integration. Real end-to-end connector
  testing = `tests/live/test_tools_integrations.py`. Use `--rich` only if you deliberately want the
  tool loop (expensive: tokens + Google calls + the 60-iteration risk).
- **Two token meters.** NIM (the traffic): lean keeps it flat; pin `--lean-model meta/llama-3.1-8b-instruct`
  to minimize. Claude (your agent tester): **launch-and-poll** — never have an LLM reason out every
  message for hours (that's the only thing that explodes). LLM-improv agents = short diversity bursts only.
- **Connectors are OAuth'd under `admin`.** Flips need `--user admin`. Score-band traffic can use any user.
- **Embedder:** retry fix landed (2026-06-30). Transient NIM degradation can slow sends to ~40s; lean
  keeps tokens capped, you just collect fewer rows. Watch `reason: embed_fail` — if it dominates, pause.
- **bge re-tune:** all thresholds are `nv-embedqa-e5-v5` geometry. Re-collect + re-tune on the
  home-server `bge-large-en-v1.5` swap — don't port the numbers.

### Adding more connectors (when asked)
- Mechanically cheap: add phrases to `INTENT_PHRASES` + a threshold + the gate + register tools + OAuth;
  extend the harness via `CONNECTORS` + `prompt_bank`. Notion/GitHub are already backend-stubbed.
- The hard part isn't compute — it's **cross-talk**: document-shaped connectors (Notion, GitHub ≈ Drive)
  overlap heavily → the latch's argmax gets wronger. Each similar connector degrades discrimination.
- **>32 tools wakes the dormant prefilter** (`TOOL_PREFILTER_THRESHOLD`); you're at ~25.
- **Sequence:** tune the 3 first → add ONE at a time → re-measure cross-talk each time → expect the
  similar ones to need the deferred margin/multi-centroid gate. Cleanest *after* the bge swap.

---

## Checklist

- [ ] Collect real volume on the 3 connectors — hundreds/band, **cold + warm** (use `--mode mixed`/`sessions`)
- [ ] Run `measure.py` → report A/B/C + `by reason` split (do NOT tune)
- [ ] Verify the **clarify fallback** — does the model ask "which X?" on cold-vague input? (fork-B depends on it)
- [ ] **Human:** pick the fork from A/B/C, then set θ_min/δ (out of scope for the collection agent)
- [ ] (later) Add connectors one at a time, re-measuring cross-talk
- [ ] (later) Re-tune θ_min/δ on the bge / home-server swap

---

## Run log

Append newest at the bottom. Template:

```
### YYYY-MM-DD — <what>
- run: <command / mode / duration / accounts>
- rows: <total> | reason {ok:_, embed_fail:_, rag_skip:_} | cold:_ warm:_
- A: <gap/overlap> · B: <margin cluster> · C: <cold/warm over-fires>
- notes: <embedder health, anomalies, decisions>
```

### 2026-06-30 — embedder retry fix (unblock)
- `embed()` had no retry → intermittent NIM 500s nulled query_emb. Added 5xx/timeout retry (e0a0206).
- before: 2/9 reason=ok · after: 12/12 reason=ok. Data collection unblocked.

### 2026-06-30 — go/no-go (all 3 connectors)
- run: one clear positive per connector, `--user admin`, lean.
- result: drive 0.825→latched_drive · calendar 0.818→latched_calendar · gmail 0.717→latched_gmail, all reason=ok.
- notes: all three OAuth'd + active under admin; green.

### 2026-06-30 — smoke (agent tester, 14 sends)
- rows: 14 | reason {ok:10, embed_fail:?, rag_skip:3 (expected on greetings)} | cold-heavy
- A: OVERLAP -0.005 (max none 0.652 vs min weak 0.647) · B: margins 0.00–0.065 · C: 2 cold over-fires, 0 warm
- notes: THIN data — directional only, not tuning-grade. Pipeline + harness validated end-to-end. Fork
  *hint* = OVERLAP+cold → conservative θ_min + clarify (confirm with volume; do not act yet).

### 2026-06-30 — harness: session mode + duration + lean added (9929e86)
- 30s sessions smoke (admin, lean, pinned llama): 1 session / 4 turns → 1 cold + 3 warm rows.
- notes: sessions are the efficient warm-row source. Healthy sends ~5–7s; a 40s/send window earlier was
  transient NIM degradation (70B circuit tripped), since recovered (all models probe ok).

### 2026-07-01 — richest-rich exerciser added (`rich_exercise.py`)
- Opposite of lean: full agent loop, real tool execution + connector round-trips + web search + write
  confirms executed for real with auto-clean. Half API (writes), half headed-UI (watch live).
- Validated live: latch-first read → `calendar_list_events`; then `calendar_create_event` →
  confirm → execute create=200 → parse id → delete=200 (Google calendar left CLEAN). `write_memory` →
  `POST /memory/write` 200 (fact tagged RICHTEST-<run>, reported for manual removal). `enable_web` PUT
  /admin/env + reload = 200.
- notes: connector tools are latch-gated → cold write turn won't fire; sessions MUST lead with a read to
  latch. Rich = short & thorough, not a multi-hour soak. UI half needs a display (`--api-only` if headless).

### 2026-07-01 — first real collection (fleet, 550 rows)
- run: `fleet.py --capture run.jsonl --admin-target 150 --score-target 400 --rate 6`
- accounts: admin (mixed sessions, 150 sends) + user (singles none_intent, 400 sends)
- rows: 550 | reason {ok: 546, embed_fail: 0, rag_skip: 4} | cold-heavy
- A: OVERLAP -0.286 (max none 0.748 vs min weak 0.462) · B: margins p50=0.016 p75=0.033 p90=0.051 max=0.127 · C: actual latched 15 (9+6w) / would-fire 122 (114+8w) — mostly cold
- notes: Embedder healthy (0 embed_fail). Admin had ~5 timeouts early then recovered. 15 over-fires at current θ (all single-winner gated — 122 would-fire shows the latch is doing heavy lifting). Margins are tight: δ < 0.05 for 90% of ambiguous rows. Fork points to COLD over-fires → θ_min + clarify fallback, NOT decay fix. Eval sets emitted: none_intent=461, weak_real=41, tie=15.

### 2026-07-01 — targeted weak_real run (150) [tie/positive killed mid-run]
- run: `run_collection --band-focus weak_real --target 150 --user admin` (lean). ~18s/send (NIM slow,
  2 timeouts). tie+positive runs were killed after weak_real finished.
- weak_real target-score dist (n=148 ok): min=0.425 p10=0.480 p25=0.554 **p50=0.610** p75=0.657 max=0.789.
  **103/148 (70%) BELOW the 0.65 floor**; 68/148 (46%) below 0.60.
- read: genuine terse requests score LOW (median 0.61). min DROPPED vs n=41 (0.462→0.425) → the OVERLAP
  is real, not a thin-data artifact. At θ=0.65: ~26% of none_intent over-fire AND ~70% of weak_real
  under-fire — **θ_min alone CANNOT separate these.** Implications: (1) clarify fallback is now ESSENTIAL,
  not optional; (2) centroids likely need terse/short phrasings (or multi-centroid) — terse genuine
  requests embed far from the full-sentence INTENT_PHRASES. Do NOT just raise θ. Human decision point.

### 2026-07-01 — FIX: nearest-example scoring + terse anchors (c3b020d, floor 194b335)
- Changed `intent_score` from cosine-vs-mean-centroid to MAX cosine over each connector's phrase
  embeddings; added terse noun-bearing phrases (23/connector). Unit-tested. Motivation: terse genuine
  scored low under the mean.
- Offline A/B (150 weak_real + 150 none_intent, same embeds, old vs new scoring):
  - weak_real med 0.614→0.658 (recall up) BUT none_intent med 0.625→0.663 (vague up ~same).
  - gap p10(weak) vs p90(none): -0.196 → -0.159 (barely moved — STILL no separation).
  - @0.65 over-fire 37%→61% (worse, new scoring hotter); @0.70 recall 18→28% / over-fire 17→15% (Pareto pt).
- DECISION: scoring change is a mild improvement, NOT the fix — the embedder fundamentally conflates
  terse-genuine vs terse-vague. Recalibrated FLOOR 0.65→0.70 (over-fire 37%→15% vs original; precision-
  biased). **The real fix is the CLARIFY FALLBACK** (accept under-fire on vague, model asks "which X?").
  θ still provisional — re-measure with more balanced data. NIM embedder 500-stormed during the probe.
- NEXT: verify + strengthen the clarify fallback (Task A rules); it now carries the recall the floor sheds.

### 2026-07-01 — clarify fallback (fork-B) implemented (19139ba)
- GAP found: `_{connector}_RULES` (with the "ask which file(s)" nudge) are `behavioral_rules` ON the
  tools → injected ONLY when LATCHED. On an under-fire turn (not latched) the model has no connector
  awareness and can't ask "which X?" — so fork-B recovery never happened.
- FIX (`stream.py`, after latch resolution): inject a latch-INDEPENDENT one-line clarify nudge for
  connectors that are ACTIVE but NOT latched — names the service, tells the model to ask ONE short
  clarifying question on a vague terse request, no schemas (KV-stable).
- Verified: control "explain a hash map" → normal answer, NO false clarify (no regression).
- UNVERIFIED: the positive case (terse under-fire → Drive-clarify). NIM was returning only `status`
  events / no model output (embedder 500-storm) during the check. **Re-verify in a stable window:**
  `POST /chat/stream {"message":"get that document"}` as admin (fresh conv) → expect a short question
  naming Google Drive. Also confirm no over-clarify on borderline turns.
