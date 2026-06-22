# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

> History note: closed batches were removed once shipped — see git log.
> Backend Audit B1–B8 (`fde4b53`), JARVIS Fallback F1–F5 (`3e27456`),
> Core-Node Protection G1–G2 (`e7839ba`), Canvas hardening I1–I3 (`41174a3`),
> create_conversation auto-wiring regression fix (`abc70af`),
> Canvas multi-turn confirm + tool-loop fixes J1–J3 (`various`),
> Google Drive integration + file tool loop K1–K10 (`65624d0`, `1a16c84`, `436554a`, `5b29500`, `9d4876b`),
> Drive stale-content + follow-up read L1–L2/M1–M6 (`b28288f`, `8fc337a`),
> Drive listing dumped on non-Drive turns N1 (`91facbe`),
> Drive keyword gate punctuation N2 (`dc18773`),
> Memory hygiene epic + safe reset S1–S4/O1–O6 (`65e8ad5`), prune hardening O7 (`ba17a39`),
> manual verification runbook (`ec5f1d0`),
> four-bug batch — memory restore / RAG scoping / embedding hygiene / test-mock tidy (`84cb78f`),
> grounding-badge persistence via `messages.render_meta` migration 044 (`0f2995a`, `87196d1`),
> calendar tools never registered at startup — `builtin/__init__.py` omitted `calendar_tools`, so all 6
> calendar tools were absent from `TOOL_REGISTRY` → never injected/dispatchable in the live agent loop
> (connector tests passed by importing the exec fns directly, masking it) (`67ec91d`).
> All fixed & verified live.

---

## Open

- `[ ]` **Reasoning trace is pipeline-level, not model chain-of-thought** — the `activity[]` trace in the `done` SSE (grounding badge → "Reasoning steps") shows the pipeline (retrieval/intent/route/budget/model/tools), not the model's internal deliberation. `meta/llama-3.3-70b-instruct` emits no native thinking tokens. Not a defect — closes the practical Dim-3 gap. Real CoT would need either a prompt-based `<thinking>` block (cheap, +tokens/latency, narrated not faithful) or a reasoning-tier model that emits traces (model/cost change). On the home server, a reasoning-capable model (e.g. a future MoE with thinking output) could close this for real. Revisit only if users ask "why did it answer that."

---

## Verification Coverage — Gaps (audited 2026-06-22)

> **Not bugs — unverified surface.** Tools + integrations are fully verified live (sweep
> **13✓ / 1 skip**, only Gmail unconnected; runbook: `backend/tests/VERIFICATION_LAUNCH.md`).
> Everything below is the **non-tool** backend surface that the live/integration/unit suites do
> **not** yet cover end-to-end. Audit = all 22 routers + 10 ARQ jobs + 5 scheduler crons mapped
> against `tests/live/`, `tests/integration/`, `tests/`.
>
> IDs `V-<group><n>`; check off as each is verified. Per-item tag:
> `[live-now]` testable against the running stack today · `[needs-infra]` needs SMTP/OCR/etc. ·
> `[timing]` fires on a cron/threshold so needs manual trigger or a wait.
>
> Already verified live (for contrast): chat SSE + `done` contract, routing/override/cache-bypass,
> RAG loop, files CRUD/dedup, auth lifecycle, health/metrics, web search, fetch_url, all file/graph
> tools, Drive, Calendar; goals **full CRUD**; notification-prefs PATCH; admin GET + secret masking;
> infra tier (migrations→047, pgvector, Redis, Neo4j).

### A. Autonomous / background pipeline — ARQ jobs (message/threshold-triggered)
> Highest-value gap. Nothing here is exercised E2E — the HTTP sweep only reads the result endpoints.

- `[ ]` **V-A1 Insight generation** `[live-now]` — `generate_insight_job` + `llm/agency.py`
  (`generate_user_insight`). Only `GET /insights` (list) is tested; `test_webhook_roundtrip` stops
  at the 202 and never asserts a `UserInsight` row appears. *Verify:* trigger via webhook / message
  threshold → assert a row lands + shows in `/insights` + injects as `[RECENT INSIGHTS]`.
- `[ ]` **V-A2 Memory compaction** `[live-now]` — `compact_memory_job` / `llm/summarizer/compact.py`
  → `UserMemoryVersion` snapshot via real 70B. Planned `test_memory_autonomy` was never written.
  *Verify:* enqueue compaction → assert a new `user_memory_versions` row + `/memory/versions`.
- `[ ]` **V-A3 Graph extraction after chat** `[live-now]` — `extract_and_store` writing Neo4j
  entities from a conversation. `query_graph` *reads* fine; the *write* path is unproven live.
  *Verify:* drive a fact-rich turn → assert `/graph/stats` entity count grew.
- `[ ]` **V-A4 Behavior profile** `[live-now]` — `update_behavior_profile_job` populating
  `UserBehaviorProfile.profile` (query_types/topics/tools/models). No endpoint asserts it fills.
- `[ ]` **V-A5 Preference extraction** `[timing]` — `extract_preferences_job` (every 50 asst msgs)
  writing `[PREFERENCES]` into `UserMemory.content`. *Verify:* enqueue the job directly.
- `[ ]` **V-A6 Auto-title** `[live-now]` — `api/chat/background.py:_auto_title` (atomic
  UPDATE…WHERE title=:default) after the 2nd message. `test_conversation_continuity` doesn't check
  the title changed. *Verify:* 2 turns → assert conversation title != default.

### B. Scheduler / cron (worker is up, but firing/registration unproven)
- `[x]` **V-B1 Scheduled-prompt execution** `[live-now]` — ✅ create (schedule alias→cron_expr) →
  `POST /scheduled-prompts/{id}/run` → `ScheduledPromptRun` recorded with terminal status → delete.
  Verified in `test_endpoints_extra.py`.
- `[ ]` **V-B2 run_memory_compaction** `[timing]` — cron `0 3 * * *`.
- `[ ]` **V-B3 run_integration_sync** `[timing]` — cron `0 */6 * * *` (id `__integration_sync__`).
- `[ ]` **V-B4 run_digest** `[needs-infra]` — `DIGEST_SCHEDULE`; per-user `email_digest` gate; SMTP.
- `[ ]` **V-B5 run_backup + `docker/backup.sh`** `[needs-infra]` — `BACKUP_SCHEDULE`; gzip dump +
  **restore rehearsal** (launch-checklist item, not done).
- `[ ]` **V-B6 Scheduler worker liveness** `[live-now]` — confirm the `scheduler` container is up
  and its 4 jobs + user schedules are registered (no leader election — must stay a singleton).

### C. Endpoints never hit by any test
- `[x]` **V-C1 Templates** `[live-now]` — `PromptTemplate` CRUD (`templates_router`). ✅ create/get/
  list/update/apply/delete verified (`test_endpoints_extra.py`).
- `[x]` **V-C2 Export** `[live-now]` — `GET /export/full` ZIP. ✅ verified — **BUG FOUND + FIXED**: declared
  `Content-Length` from `zip_buf.tell()` (0 after rewind) → uvicorn aborted the connection and broke the
  next keep-alive request. Fixed in `api/export.py` (length from actual bytes). Commit `36c892e`.
- `[x]` **V-C3 Unified search** `[live-now]` — `GET /search?q=` fan-out. ✅ shape + finds freshly written
  memory. (path is `/search`, not `/api/search`.)
- `[x]` **V-C4 Conversation ops** `[live-now]` — ✅ PATCH, export (md+json), `?q=` search, delete, file
  attach/detach all verified.
- `[ ]` **V-C5 Admin mutations** `[live-now]` — `PUT /admin/env` + `POST /admin/env/reload` (live
  config change), memory reset (soft/hard) + `/memory/versions` + `/memory/restore`, cost-limit set.
  → Phase 3.
- `[~]` **V-C6 Invite gate** `[live-now]` — ✅ issuance + listing + register-with-token verified.
  Consumption-enforcement (`REQUIRE_INVITE=true` blocks token-less register) → Phase 3 env-flip test.

### D. Reliability invariants (matter for launch; all untested)
- `[ ]` **V-D1 Fallback chain** `[live-now]` — chosen → reasoning → coder → llama; all-fail → 503
  + `ALL_MODELS_FAILED` counter. Planned `test_fallback` never written. *Verify:* bad
  `model_override` / pre-tripped breaker.
- `[ ]` **V-D2 Circuit breaker** `[live-now]` — 5 failures → open, 90s cooldown, Redis `cb:open:*`
  persisted, restored on startup.
- `[ ]` **V-D3 Rate limiting** `[live-now]` — chat 15/60s/user; per-model llama15/coder10/reason5
  → 429; fail-open on Redis down.
- `[ ]` **V-D4 Cost cap** `[live-now]` — rolling `cost_window_days` → **402** with label
  (`$x / $y 30d`); self-disable blocked. *Verify:* set a tiny limit via admin, exceed.
- `[x]` **V-D5 Memory conflict** `[live-now]` — ✅ `scan` (200) + `resolve` (keep_a) verified; scan is
  LLM-judged so detection is best-effort (test resolves only if flagged).

### E. Optional / infra-dependent
- `[ ]` **V-E1 Real OCR** `[needs-infra]` — `IMAGE_OCR_ENABLED` on → upload image/scanned-PDF →
  `File.ocr_text` populated, chunks embedded (unit-mocked only today).
- `[ ]` **V-E2 Notifications dispatch** `[needs-infra]` — actual email (SMTP/MailHog) + web push
  send via `services/notification.py:notify()`; only prefs/subscribe contract is tested.
- `[ ]` **V-E3 Digest email** `[needs-infra]` — see V-B4.
- `[ ]` **V-E4 Backup → restore rehearsal** `[needs-infra]` — see V-B5.
- `[x]` **V-E5 Re-embed** `[live-now]` — ✅ `POST /admin/re-embed` accepted (200/202). Verified.

### Run log — autonomous verification (2026-06-22)
> New suites under `tests/live/`. Bugs found are fixed aggressively + re-verified, each in its own commit.

- **BUG-V1 (fixed, `36c892e`)** — `GET /export/full` crashed with `RuntimeError: Response content
  longer than Content-Length`: header used `zip_buf.tell()` (0 after `_build_zip` rewinds) while the
  body was the full ZIP → uvicorn aborted the connection (also broke the next keep-alive request).
  Fixed: Content-Length from `len(zip_buf.getvalue())`. `api/export.py`.
- `[ ]` **BUG-V2 (minor, open)** — `retriever.store_exchange` raises `ForeignKeyViolationError` on
  `message_embeddings.message_id` when a conversation/message is deleted before its async embed task
  commits (race). Already caught + logged + rolled back (non-fatal, no user impact) but noisy.
  *Candidate fix:* skip the embed insert if the message no longer exists, or treat FK violation as a
  debug-level skip. `llm/retriever/queries.py:store_exchange`. Low priority.
- Phase 1 (endpoint contracts): **10/10 live pass** after BUG-V1 fix.

### Plan
- **Tier 1 (`[live-now]`)** → build a new live suite `tests/live/test_autonomy_and_reliability.py`
  covering A1–A4, A6, B1, B6, C1–C6, D1–D5, E5. Closes most of A–D against the running stack.
- **Tier 2 (`[needs-infra]` / `[timing]`)** → A5, B2–B5, E1–E4: document as infra/cron-gated in the
  runbook; verify opportunistically (MailHog for mail, flag flip for OCR, manual job enqueue for cron).

---

## Decisions — Home-Server Port & #19 Vision (resolved 2026-06-17)

> Design decisions, not bugs. Settled with the user; drive the Mixtral port + #19.
> Legend: ✓ confirmed · ✎ refined · ⚑ important.

### Settle-first order

```
1. A2  tool_calls actually work on llama.cpp + Mixtral GGUF — highest risk, blocks the agent loop
2. A1/A4  llama.cpp + Q4_K_M + TPS check — also SPECTRA Gate 1 baseline (one measurement, both uses)
3. A3/B1  32k context + 1024-d embedder — config correctness; avoids overflow + re-embed
4. C1  unify image paths through OCR — prevents the silent paste-path break
```

### A. Serving / port

- **A1 ✓ runtime = llama.cpp / GGUF** — right for P40 (Pascal). SPECTRA also targets
  llama.cpp → production + research align on one runtime.
- **A2 ⚑ verify tool-calling FIRST** — the entire agent loop (`llm/nim.py` +
  `llm/service/stream.py`) depends on native `tool_calls`. llama.cpp tool-calling is
  model+template-dependent and finicky; test the actual Mixtral GGUF chat template
  early. Prompt-based emission is the fallback net. Highest-risk item.
- **A3 ⚑✓ context = 32768** — Mixtral 8x7B/8x22B trained limit is 32k. **Supersedes
  the earlier ~50K/84K figures** (those were VRAM-KV-capacity estimates; 32k is the
  real trained ceiling). Set `config.py CONTEXT_WINDOWS` Mixtral entries to 32768 and
  size the budget allocator off it. Silver lining: 32k KV is small (~2–4 GB q8, ~2 GB
  q4) → eases VRAM pressure.
- **A4 ✓ Q4_K_M + q4 KV cache** — at 32k, q4-KV recall cost is mild. "Confirm TPS
  before 1B" == SPECTRA Gate 1 baseline; one measurement serves both.
- **A5 ✓ collapse to one Mixtral; router telemetry-only** — can't fit 3 models. Router
  keeps a real job only if some cloud-NIM overflow remains; if overflow is fully out,
  it's telemetry-only.
- **A6 ✓ relax NIM-isms** — make `NVIDIA_API_KEY` guard (`config.py:144`) optional when
  `NIM_URL` is localhost/LAN; rename `NIM_*`/`NVIDIA_*` later (cosmetic, low priority).

### B. Embedding

- **B1 ✓ stay 1024-d (`bge-large-en-v1.5`)** — avoids the `EMBEDDING_DIM` change →
  no migration, no full re-embed of `FileChunk` + `MessageEmbedding`. (`e5-large-v2`
  also 1024; `nomic` is 768 → would force re-embed.)
- **B2 ✓ embedder GPU now, CPU at 8x22B** — query embedding is hot-path (GPU); index
  embedding is async. Move to CPU as the relief lever when 8x22B maxes VRAM.

### C. Vision / OCR (#19)

- **C1 ⚑✓ route paste-path through OCR** — `stream.py:206-211` breaks on a text-only
  server. Unify BOTH image entry points (Library upload + chat `image_b64` paste)
  through PaddleOCR → text. One mechanism, two entry points.
- **C2 ✓ English/Latin OCR first** — Filipino langs (Tagalog/Bisaya/Hiligaynon) are
  Latin-script → already covered; no separate lang pack needed.
- **C3 ✓ forward-only** — new uploads only; add a manual re-process trigger later if
  needed.
- **C4 ✓✎ PNG/JPG/WebP; downscale longest edge ~2500–3000px** — bumped from 2000px:
  dense-text scans lose accuracy below ~2000px. (50 MB upload cap already exists.)
- **C5 ✓ scanned/image-only PDFs → OCR fallback** — if pypdf text is empty, fall
  through to PaddleOCR per page. Later enhancement.
- **C6 ✓ no-text image → `ready`, 0 chunks** — filename-searchable; never `error`.
- **C7 ✓✎ store plain text only now** — bbox storage is cheap and aids future #22 / UI
  highlighting (low-cost keep if reconsidered); deferring is consistent with lean.
  Thumbnails generated lazily from the stored original via `download_file`.
- **C8 ✓ `IMAGE_OCR_ENABLED` default false** — off until a CPU OCR backend is present;
  safe no-op (images persist, filename-searchable).

### D. SPECTRA & future

- **D1 — what SPECTRA is (grounding for the VRAM math):**

```
NOT speculative decoding. NOT a draft model. NOT separate weights.
(Speculative decoding is HALO's thing — different project. Don't conflate.)

SPECTRA = a regime-adaptive inference MIDDLEWARE between llama.cpp and the GPUs.
Lean v1 mechanism (sparse-saturated regime only):
  when live PCIe load > threshold θ:
    1. forecast experts needed ~30-50 tokens ahead (from gate scores)
    2. compress them 4-bit → 2-bit on the fly (Poly-Morpher)
    3. async-prefetch the 2-bit clones into a per-GPU SHADOW CACHE
    4. route execution to the local clone → skip the PCIe fetch
  below θ: full 4-bit, no action.

The ~10GB = the shadow cache (~2.5GB/card × 4) holding compressed expert clones,
REDUNDANT with the resident 4-bit experts. A cache+routing layer over the
already-loaded Mixtral, NOT extra model weights.
"Elastic under context pressure" = the cache partition shrinks to yield VRAM to KV.
Optimizes decode SPEED + GPU util (~2-2.5x TPS target). SPENDS VRAM to buy speed —
NOT a capacity tool.
```

  VRAM model: a **~10 GB elastic shadow-cache reservation, active only under load,
  tunable in size.** ⚑ Numbers are **UNVALIDATED** (gates haven't run) — 10 GB and
  2.5x are hypotheses, cache size is a parameter. Do not hardcode as fact. Full
  grounding: `SPECTRA_CONTEXT.md`.

- **D2 ✓ #22 deferred — concrete trigger:** log image-search queries returning no/poor
  hits *where the relevant content is non-text* AND the user re-finds it manually.
  Repeated → trigger. ColQwen2 (docs/screenshots) stays the pick.
- **D3 ✓ prefer a vision-native 145B if otherwise even** — candidates: Llama 4
  (natively multimodal MoE), Qwen-VL MoE variants. If chosen, #19's separate vision
  role collapses into the chat model.
