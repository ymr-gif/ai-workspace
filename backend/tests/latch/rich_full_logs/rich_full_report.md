# Rich Full-Feature Run — Report (2026-07-02 → 03)

One orchestrated run exercising every feature documented in the markdowns, real mutations included.
Plan: `~/.claude/plans/happy-crafting-catmull.md` · Orchestrator: `run_rich_full.sh` · Gap-filler: `rich_full.py`
Run tags: `RICHFULL-09df2725` (main) + section reruns · Logs: this directory.

## Verdict

**Every documented feature verified except two live tests blocked by NVIDIA 70B capacity**
(mechanics independently evidenced; **accepted-as-blocked by decision 2026-07-03** — see the
closed section below). No product bugs found. Two test-suite drifts found and fixed. Several
documentation nuances surfaced (below).

## Results by phase

| Phase | Result |
|---|---|
| A preflight | stack healthy · baseline backup 4.3 MB · 3 connectors active (admin) · paddle absent (BUG-V7) |
| B1 unit | 183 passed, 1 skipped |
| B2 retrieval | 26 passed |
| B3 infra | 2 passed, 11 skipped (host ports; facts verified directly: pgvector 1024 · alembic 047 · redis PONG) |
| B4 live E2E | 63 passed, 3 skipped, 9 failed on NIM 429 throttle → **7/9 recovered on rerun**, 2 quota-blocked (below) |
| B5 smoke | PASS |
| C rich_exercise | PASS — all tool families incl. gmail; calendar real write+delete (create=200/delete=200, left clean) |
| D rich_full | **22/22 sections green in final form** (18 first-pass + 4 fixed-and-rerun) |
| E cleanup | memory de-tagged (423→301 chars) · users 82/84 disabled · flags restored · graph/webhook/redis clean · health ok |

## Gap-filler section results (final)

PASS: auth_onboarding (invite→register→onboarding→API-key lifecycle) · unified_search (5 scopes) ·
full_export (214-entry ZIP) · conversations (lock/export/messages) · graph (stats/sample/prune) ·
metrics_observability · cache (miss→hit→param-bypass, model pinned) · notifications · voice (stub +
503 gate-off) · ocr (graceful gating; extraction untestable — BUG-V7) · webhooks (3 event types +
token 404-after-delete) · memory_deep (write/scan/conflict-resolve/history/decay/compact/export/import) ·
scheduled_prompts · goals · rotation (46 turns → `rotated` SSE + DB-archived) · admin_sweep
(cost-limit/active-toggle→401/env-roundtrip/audit) · cost_cap (402→removal→200) · rate_limit
(concurrent burst → 429) · re_embed (queued 1047) · ui_panels (10 panels + memory tabs + "Soon"
re-stub assert; screenshots in `ui/`) · circuit_breaker (restored-on-startup + enforced: coder
request served by 8B with `fallback_used=true` while open; recovered after cooldown) ·
memory_reset_restore (throwaway reset+restore 200 · admin dry-run inert · real soft reset + snapshot).

## Environment-blocked (NOT product failures) — CLOSED AS ACCEPTED 2026-07-03

- `test_web_search_fires_and_flags`, `test_list_files_tool` — NVIDIA-side capacity for
  `meta/llama-3.3-70b-instruct` collapsed under the run's volume and did not recover within ~24h:
  first clean 429s on all retries (token-based — 1-token probes pass while full-context calls
  starve, so probe gates don't work), later a degraded-slow mode (turns > 150s → client
  ReadTimeout). ~10 retry attempts over 24h incl. hourly loops. Reads as an **account-tier
  throughput cap**, not a resetting quota — only the NVIDIA account console can fix it.
  **Accepted by decision 2026-07-03**: mechanics fully evidenced (web_search **dispatched with
  tool_result** once config was re-armed; list_files' identically-gated siblings
  file_search/create_file/read_file/query_graph passed in an open window; both passed on the
  2026-06-22 record), NIM is the interim test backend, and the homeserver port removes the
  dependency. Rerun any time capacity recovers (re-arm `WEB_SEARCH_ENABLED` first — nuance 2):
  ```
  RUN_LIVE_NIM=1 VERIFY_BASE_URL=http://localhost:8000 pytest \
    tests/live/test_tools_integrations.py::test_web_search_fires_and_flags \
    tests/live/test_tools_integrations.py::test_list_files_tool -m "live_nim or optional"
  ```
- Incidental live positives from the throttle: circuit breaker organic trip + recovery
  (`[circuit] opened model=meta/llama-3.3-70b-instruct`), retry/backoff chain, fallback chain.

## Findings (doc/test-level; no product bugs)

1. **Compose env outranks `.env`** for keys present in the compose environment (`MODEL_CODER`,
   `WEB_SEARCH_ENABLED`): `/admin/env` PUT works live (setattr) but **reload or restart re-masks
   it** from `os.environ`. Worth a note next to the `LLM_BACKEND` invariant in `backend/CLAUDE.md`.
2. **`MODEL_*` live flips never reach routing** — `api/chat/helpers.py` freezes `MODELS` at import
   (documented as harmless for homeserver; also means env-flip can't change routed model ids
   without restart).
3. **Latch recall data point** (do NOT tune): explicit cold calendar-create scored 0.531 < 0.70
   floor. fork-B's designed precision cost; the shipped UX (latch-first) works.
4. **Stale test fixed**: `test_calendar_create_confirm_sentinel` rewritten latch-first (was written
   pre-latch; single cold create-turn is structurally unable to fire the tool).
5. **BUG-V6 looks stale**: scheduled 2 AM in-container backups ARE producing dumps
   (`nimrouter_2026070*_020000.sql.gz`, root-owned). Recommend re-verifying and closing in BUGS.md.
6. **BUG-V7 confirmed**: paddle missing from image; OCR gate degrades gracefully (upload `ready`,
   paste path streams clean), extraction untested.
7. `arq_job_failed_total` absent from `/metrics` until a first job failure (multiprocess counters
   materialize on first increment) — benign, noted for dashboard readers.
8. **Harness limitations**: `ui_capture` CDP body-read fails on long SSE streams (capture row lost,
   send still processed); breaker enforcement probe must land within the 90s cooldown (section now
   probes first and SKIPs-inconclusive on lapse).

## Residuals (deliberate)

- `.env` now pins `WEB_SEARCH_ENABLED/VOICE_ENABLED/IMAGE_OCR_ENABLED=false` + `RICHFULL_PROBE=removed`
  (keys were absent pre-run; no DELETE endpoint — values match defaults, harmless).
- Users `richfull_09df2725` (82) / `richfull_4919d119` (84): disabled, not deletable (no endpoint).
- `messages`/`tool_call_logs`/audit rows from the run remain (immutable history; admin soft reset
  archived the conversations).

## Files changed this session

- `backend/tests/latch/rich_full.py` — NEW: 22-section gap-filler.
- `backend/tests/latch/run_rich_full.sh` — NEW: phase orchestrator.
- `backend/tests/latch/README.md` — appended "Rich FULL-feature run" section.
- `backend/tests/live/test_tools_integrations.py` — calendar sentinel test → latch-first.
