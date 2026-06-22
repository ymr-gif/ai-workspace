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

- `[x]` **V-A1 Insight generation** `[live-now]` — ✅ webhook (`external.data`) →
  `process_webhook_job` → `generate_user_insight` → `UserInsight` row appears in `/insights`.
  `test_autonomy.py::test_insight_generated_from_webhook`.
- `[x]` **V-A2 Memory compaction** `[live-now]` — ✅ `POST /memory/compact` → new `UserMemoryVersion`
  visible in `GET /memory/history`. `test_autonomy.py::test_compaction_creates_version`.
- `[x]` **V-A3 Graph extraction after chat** `[live-now]` — ✅ fact-rich chat → `/graph/stats`
  entity count grows from 0. `test_autonomy.py::test_graph_extraction_after_chat`.
- `[x]` **V-A4 Behavior profile** `[DB-verified]` — ✅ after 2 chats, `user_behavior_profiles.profile`
  populated (`tools_used`/`models_used`/`query_types`/`topic_keywords`/`total_messages`). Verified
  via psql (no HTTP surface — recorded in run log).
- `[x]` **V-A5 Preference extraction** `[DB-verified]` — ✅ enqueued `extract_preferences_job` directly
  via ARQ pool → wrote a correct `[PREFERENCES]` block (`verbosity: concise`, `response_style: direct`)
  to `user_memory.content`. Verified via psql + arq logs.
- `[x]` **V-A6 Auto-title** `[live-now]` — ✅ 2nd turn in a conversation → title changes off the raw
  first message. `test_autonomy.py::test_auto_title_after_second_message`.

### B. Scheduler / cron (worker is up, but firing/registration unproven)
- `[x]` **V-B1 Scheduled-prompt execution** `[live-now]` — ✅ create (schedule alias→cron_expr) →
  `POST /scheduled-prompts/{id}/run` → `ScheduledPromptRun` recorded with terminal status → delete.
  Verified in `test_endpoints_extra.py`.
- `[x]` **V-B2 run_memory_compaction** `[fixed]` — cron `0 3 * * *`. Was silently dead (no arq pool,
  **BUG-V5**); after the fix it enqueues compaction for eligible users. Verified by direct invoke.
- `[x]` **V-B3 run_integration_sync** `[fixed]` — cron `0 */6 * * *`. Same BUG-V5; now "integration
  sync queued for 2 sources". Verified by direct invoke.
- `[~]` **V-B4 run_digest** `[needs-infra]` — gated off (`DIGEST_ENABLED=False`, `SMTP_HOST=''`);
  invoking it returns cleanly (graceful no-op). Full send path needs SMTP (MailHog).
- `[~]` **V-B5 run_backup + `docker/backup.sh`** — ✅ **host-run backup works** (1.4 MB gzip, 26 tables,
  pruning OK). ❌ **BUG-V6**: the scheduled in-container `run_backup` is dead (`backup.sh` not in the
  image + no docker CLI + pgbouncer can't pg_dump). Restore-rehearsal needs a staging DB.
- `[x]` **V-B6 Scheduler worker liveness** `[live-now]` — ✅ container up 3d; all 5 jobs registered
  (sync_schedules 5-min, compaction 3am, backup, integration-sync 6h) + arq pool now ready.

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
- `[x]` **V-C5 Admin mutations** `[live-now/unsafe-isolated]` — ✅ `PUT /admin/env` + reload
  (harmless probe key, host `.env` untouched), memory **hard** reset (memory + Neo4j graph cleared)
  + `/memory/versions` + `/memory/restore` (snapshot → restored), cost-limit set/revert. All on a
  throwaway user. Verified via run scripts.
- `[x]` **V-C6 Invite gate** `[live-now]` — ✅ issuance/listing/register-with-token; and after
  **BUG-V4 fix**, `REQUIRE_INVITE=true` (live reload) blocks token-less register (403) and a valid
  token registers (201). Verified via env-flip script.

### D. Reliability invariants (matter for launch; all untested)
- `[x]` **V-D1 Fallback chain** `[unsafe-isolated]` — ✅ tripped the **coder** breaker (Redis +
  restart → `restore_circuit_state`), then a coder-routed chat fell back to reasoning with
  `done.fallback_used=True` + `Falling back → ...` status. Breaker cleared + coder restored healthy
  (no lasting impact). Note: a *bad* `model_override` is resolved to a valid model, not fallback.
- `[x]` **V-D2 Circuit breaker** `[unsafe-isolated]` — ✅ in-container: 5 `record_failure` → `is_open`
  True + Redis `cb:open:*` set; `record_success` → reset; `restore_circuit_state` reloads from Redis
  on restart. Trip logic tested on a **fake** model (zero blast radius); restore tested on coder.
- `[x]` **V-D3 Rate limiting** `[live-now]` — ✅ >15 chat posts/60s on a throwaway user → 429.
  `test_reliability.py`.
- `[x]` **V-D4 Cost cap** `[live-now]` — ✅ near-zero cap on a throwaway user → **402** with label
  `Cost cap reached ($x / $y 30d)` on the **stream** path. `test_reliability.py`. (See BUG-V3.)
- `[x]` **V-D5 Memory conflict** `[live-now]` — ✅ `scan` (200) + `resolve` (keep_a) verified; scan is
  LLM-judged so detection is best-effort (test resolves only if flagged).

### E. Optional / infra-dependent
- `[~]` **V-E1 Real OCR** `[needs-infra]` — `IMAGE_OCR_ENABLED=False`. ⚠️ **BUG-V7**: `paddleocr` is
  installed but `paddlepaddle` (the `paddle` backend) is **not** — the `requirements.txt` pin dropped
  explicit `paddlepaddle` assuming it's transitive, but it isn't pulled. Enabling OCR would fail.
  Harmless while OCR is off (default), but blocks #19. Unit-mocked OCR tests still pass.
- `[~]` **V-E2 Notifications dispatch** `[needs-infra]` — no `SMTP_HOST` / VAPID on this stack, so the
  email + web-push send paths can't run live; covered by `tests/test_notifications.py` (mocked).
- `[~]` **V-E3 Digest email** `[needs-infra]` — see V-B4 (gated off, graceful no-op; needs SMTP).
- `[ ]` **V-E4 Backup → restore rehearsal** `[needs-infra]` — dump verified (V-B5); restore over a
  **staging** DB not run (restoring over live is destructive).
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
- Phase 2 (autonomy): **4/4 live pass** (`test_autonomy.py`); A4 behavior-profile + A5 preferences
  verified via psql/ARQ (no HTTP surface) — both jobs produce correct rows. No bugs found.
- `[ ]` **BUG-V3 (design gap, open)** — nonstream `POST /chat` is **stateless**: it calls
  `service.generate_response(message, rid)` with no `db`/`user`, so it persists no message, records
  no cost/tokens, and the **cost cap + history + RAG/memory/tools do not apply**. A user could spend
  NIM tokens with no accounting or cap via `/chat` (rate-limited, but uncapped). `/chat/stream` is the
  full stateful path. *Decide:* either wire cost-accounting/cap into `/chat`, or document `/chat` as a
  deliberately-ephemeral endpoint and ensure clients use `/chat/stream`. `api/chat/router.py:24`.
- **BUG-V4 (fixed, `945f67a`)** — `auth/router.py` used `from config import REQUIRE_INVITE` (frozen at
  import), so flipping `REQUIRE_INVITE` via `/admin/env` reload didn't gate registration live. Switched
  to call-time `config.REQUIRE_INVITE`; verified 403/201 live. (Gate already worked on restart.)
- Phase 3 (reliability + unsafe-isolated): **D3/D4 4/4 live pass** (`test_reliability.py`); D1/D2
  (fallback + breaker), C5 (env PUT/reload + memory reset/restore), C6 (invite gate) verified via
  isolated run scripts — fake model + throwaway users + immediate restore (coder breaker cleared,
  caps reverted, env reverted, no lasting impact). Found BUG-V3 + fixed BUG-V4.
- **BUG-V5 (fixed, `6c98c84`)** — the scheduler worker never called `init_arq_pool`, so
  `get_arq_pool()` was None and **daily memory compaction + 6h integration sync silently no-op'd**
  ("no arq pool"). Added `init_arq_pool(REDIS_URL)` to `scheduler_worker.main()`; verified both now
  enqueue. (The most impactful find — two background jobs were effectively dead.)
- `[ ]` **BUG-V6 (open)** — the **scheduled backup is dead**: `run_backup` shells out to
  `docker/backup.sh`, which isn't in the image and needs `docker compose` + pg_dump (neither present
  in the scheduler container; `DATABASE_URL` points at pgbouncer, which can't pg_dump). Host-run
  `bash docker/backup.sh` works. *Fix options:* add `postgresql-client` to the image + dump the
  `postgres` host directly, or run backup as a host cron / sidecar. Needs a deploy decision.
  `services/scheduler_worker.py:run_backup`.
- `[ ]` **BUG-V7 (open)** — `paddlepaddle` missing from the image (`paddleocr` present, `paddle`
  absent); the `requirements.txt` pin assumed it's transitive. OCR (`IMAGE_OCR_ENABLED`, #19) would
  fail if enabled. Harmless at the default (OCR off). *Fix:* re-add `paddlepaddle` to requirements +
  rebuild. `backend/requirements.txt`.
- Phase 4 (infra/cron): B2/B3 fixed (BUG-V5), B5 host-backup verified + BUG-V6, B6 liveness ✓,
  digest graceful no-op; E1/E2/E3/E4 are needs-infra (SMTP/VAPID/paddle/staging-DB) — documented.

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
