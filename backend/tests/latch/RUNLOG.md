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

### YYYY-MM-DD — <next real collection run>
- run:
- rows:
- A: · B: · C:
- notes:
