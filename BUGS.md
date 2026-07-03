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
> Verification audit 2026-06-22 — 7 bugs found + fixed: export Content-Length (`36c892e`),
> store_exchange delete-race log (`b48a268`), cost-cap on nonstream `/chat` (`49cb6ea`),
> live `REQUIRE_INVITE` reload (`945f67a`), scheduler arq-pool init → compaction/sync were dead (`6c98c84`),
> scheduler backup pg_dump + postgresql-client-16 (`443df8e`), OCR paddle log/requirements note (`75370ae`).
> De-keyword fallout fixes 2026-06-23 (`d3b73a7`): file-handling rule reworded so "list" no longer
> suppresses `list_files`; global-file RAG fallback decoupled from file-tool injection
> (`context_only_file_ids`); `write_memory` schema description hardened ("RARE action") to curb
> spurious confirm cards.
> Drive greeting over-fire (`drive_list_files` dumped on "ehllo") 2026-06-28 — session **intent latch**
> (Q3 Task B): Drive schema withheld until an embedding-cosine Drive-intent signal latches the session;
> Task A (abstention prompt) measured ineffective first, so the schema is removed pre-intent, not just
> discouraged. `drive_intent.py` (`3719d12`, `fcb9b4e`).
> Calendar + Gmail had the *same* capability-only greeting over-fire (`calendar_list_events` /
> `calendar_search_events {"query":"hi"}` on "ehllo") 2026-06-28 — generalized the latch to a
> **per-connector single-winner** gate in `connector_intent.py` (`f6b1a68`; `drive_intent.py` folded in).
> Both: cold greeting case structurally fixed (schema absent pre-intent). Open residuals → Open list below.
> All fixed & verified live.
> `write_memory` fires on greetings → empty reply + junk confirm card 2026-06-28 — gated on explicit
> memory intent (`db AND is_reasoning AND _needs_memory_tool`); embedding-cosine gate tried + rejected
> (greetings ~0.58 inside the real-memory range); implicit prefs still captured by the background
> pipeline; residual: legit write still ends in an empty bubble + card (accepted) (`fcc52ec`).
> 70B streaming `stream_network_error attempt=0` → silent fallthrough to deepseek 2026-07-02 — bare
> float `httpx.AsyncClient(timeout=30)` made 30s the time-to-first-token on streams; the 70B's slow
> TTFB always tripped it. New `STREAM_READ_TIMEOUT` (120s) applied per-request in `call_stream`;
> connect/write/pool stay 30s (`2229aa8`).
> **2026-06-28 (post-latch): Drive/Calendar/Gmail moved to UI stubs** (`ENABLED_CONNECTOR_TYPES = []`). The latch code (`connector_intent.py`) is now harmless dead code — no active connectors can exist, so it never fires.

---

## Open

- `[~]` **Connector intent-latch — residual leaks (Drive / Calendar / Gmail)** — **MOOT (2026-06-28):** connectors are UI-stubbed (`ENABLED_CONNECTOR_TYPES = []`), the latch never fires. Re-open if re-enabled. Original detail: the latch makes the *cold* greeting case structurally impossible, but three weaknesses remain: **(1) post-latch trivial turns** — once a connector is latched, `thanks`/`ok` can still fire its tools (schema legitimately present; the per-connector `_RULES` prompt is the only guard and stays weak on the 70B). **(2) sticky-latch session-poisoning** — the latch is sticky 1h and the centroid can't cleanly separate connector-intent from *substantive task/coding imperatives* ("help me debug" ≈ 0.66 vs the drive centroid; gate accuracy ~32/40), so a false latch on a coding turn flips a connector on for the rest of the session (single-winner caps the blast radius at **one** connector, not all three). Mitigation: `FLOOR_THRESHOLD` (0.65) added 2026-06-29 — rejects weak winners that only "won" because every score was low ("help me debug" at ~0.66 clears per-connector drive 0.60 but NOT the floor 0.65, so no latch). The floor complements the per-connector thresholds; the full condition is `scores[winner] >= max(INTENT_THRESHOLDS[winner], FLOOR_THRESHOLD)`. Other mitigations considered (decay latch, 2-class gate, 8B pre-pass) deferred. **(3) verification rigor** — the cold-case tests are structural/deterministic (firm), but the probabilistic 70B behavioral tests were run once each, not the 3–5 repeats originally specced. Shipped record: `HANDOFF.md` → "COMPLETED PHASE: Q3 Task B" + the two 2026-06-28 History rows.
- `[~]` **Connector latch can't separate terse-genuine from terse-vague — no clean threshold (over-fire vs under-fire)** (data-confirmed 2026-07-01; **MITIGATED via fork-B 2026-07-02**)
  - **Resolution (2026-07-02):** fork-B shipped and closed the data effort. `FLOOR_THRESHOLD=0.70` (precision-biased) + a latch-independent **clarify fallback** (`stream.py:403`, `19139ba`, light-tuned 2026-07-02) — connectors active-but-unlatched → the model asks ONE service-naming question instead of under-firing into silence. Verified live 2026-07-02. Full decision: `plans/connector-latch-data-plan.md` → "Phase 4 — DECIDED". **Residual (accepted, why still `[~]` not `[x]`):** recall is traded for precision by design — genuine terse requests below 0.70 get a clarifying question, not a tool. The embedder wall is unchanged; full recall recovery waits on a better embedder (bge re-tune). `nv-embedqa` collection is CLOSED.
  - **Symptom:** the embedding-cosine latch conflates genuine terse requests ("read that file", "any new mail") with connector-adjacent vague turns ("find my things", "check my stuff"). Any single floor either over-fires on vague or under-fires on genuine — the bands overlap.
  - **Evidence (offline A/B, 150 weak_real + 150 none_intent, same embeds; `backend/tests/latch/RUNLOG.md` 2026-07-01):** weak_real median 0.61 (mean) / 0.66 (nearest-example); none_intent reaches 0.71–0.77. Gap p10(weak) vs p90(none) = **−0.196 (mean) → −0.159 (nearest-example)** — still no separation. At floor 0.65 the new scoring over-fires 61% of vague; at 0.70, over-fire 15% / genuine recall 28%.
  - **Root cause:** the embedder (`nv-embedqa-e5-v5`) does not linearly separate these short phrasings — a representational limit, not a scoring bug. Same wall the `write_memory` gate hit (embedding "too weak to separate" → fell back to keywords; see that entry above).
  - **Files:** `backend/llm/tools/connector_intent.py` (`intent_score`, `INTENT_PHRASES`, `INTENT_THRESHOLDS`, `FLOOR_THRESHOLD`); `backend/llm/service/stream.py:_resolve_connector_latches` (gate/flip); abstention rules `_DRIVE_RULES`/`_CALENDAR_RULES`/`_GMAIL_RULES` in `backend/llm/tools/builtin/{drive,calendar,gmail}_tools.py`; harness `backend/tests/latch/`.
  - **Done so far:** mean-centroid → nearest-example (max over phrase embeddings) + terse anchors (`c3b020d`) — lifted genuine recall but lifted vague ~equally (marginal). Recalibrated FLOOR 0.65→0.70 (`194b335`), precision-biased (over-fire 37%→15%, sheds recall).
  - **Solutions / how to improve (ranked):**
    1. **Clarify fallback (primary) — ✅ SHIPPED 2026-07-02 (`19139ba`, light-tuned).** Accept under-fire on vague; the model asks "which document/calendar/inbox?" so the user's next turn scores clean. **CRITICAL GAP found 2026-07-01 (now fixed):** the `_{connector}_RULES` (which hold the "ask which file(s)" nudge, e.g. `drive_tools.py:_POST_LISTING`) are attached as `behavioral_rules` **on the tools**, so they were injected **only when the connector is LATCHED** — absent on the under-fire turn where we need them. Fix shipped: a lightweight latch-independent one-line clarify nudge injected in `stream.py:403` for connectors ACTIVE but NOT latched (keeps schemas withheld + KV-cache stable). Verified live 2026-07-02 (vague "get that thing i need" → model named Drive+Gmail, asked one question; control tech Qs → no false clarify).
    2. **Hybrid explicit signal (memory-write precedent).** OR the semantic score with a cheap deterministic cue — possessive + connector-noun ("my file/document/spreadsheet"→drive; "my calendar/schedule/meeting"→calendar; "my email/inbox/mail"→gmail). Deterministic latch for the unambiguous cases, semantic for the rest; mirrors `_needs_memory_tool` (`context.py:42`).
    3. **Threshold re-tune with balanced volume** — the 0.70 floor is provisional (one 150/150 sample).
    4. **bge re-tune** — the home-server embedder swap changes geometry; re-measure (may separate differently).
    5. Deferred alternatives: decay latch, 2-class gate, 8B pre-pass.
- `[ ]` **Stateless chat endpoints: spend is unmetered (V3 residual) — and `/v1/chat/completions` has no cap check at all** (parked 2026-07-03, needs decision)
  - **Status split:** `49cb6ea` (2026-06-22 audit) added the `_check_cost_cap` 402 pre-flight to nonstream `POST /chat` — a capped user IS blocked there. But `/chat` still records **no tokens/cost** (stateless, no `Message` rows), so its spend never accrues to the rolling window: a user under their cap can burn NIM credits via `/chat` invisibly, and the cap only tightens from their *streaming* usage. The OpenAI-compat `POST /v1/chat/completions` (`api/compat.py`) is worse: **neither cap check nor accounting** (verified 2026-07-03 — no `_check_cost_cap`/cost refs in the file).
  - **Severity:** low today (invite-gated, trusted users; both endpoints are conveniences) — but it's a billing-enforcement hole to close before anything public.
  - **Options:** (a) add usage recording to both (mirror `background.py` token/cost calc; no conversation persistence needed — a usage-ledger row suffices); (b) add `_check_cost_cap` to compat + accept unmetered spend documented; (c) admin-gate or remove the endpoints. Decision is the user's; (a) is the complete fix.
  - **Files:** `backend/api/chat/router.py` (cap check present, accounting absent), `backend/api/compat.py` (both absent), `backend/api/chat/helpers.py:_check_cost_cap`, `backend/api/chat/background.py` (the cost-calc to mirror).
- `[ ]` **Pre-prod launch gate — env hardening is deploy-time work, never covered by test runs** (parked 2026-07-03)
  - The 2026-07-03 rich-full run verified the entire feature surface on the dev stack; what it *cannot* verify is the deploy-time checklist in `backend/tests/VERIFICATION_LAUNCH.md`: secrets off defaults (`NEO4J_PASSWORD=changeme`, Grafana `admin/admin`, Postgres default), `JWT_SECRET_KEY` ≥32, `INTEGRATION_SECRET` + prod `INTEGRATION_REDIRECT_BASE`, TLS via `nginx.prod.conf`, firewall closing 8000/3001/9090/7474, then smoke + off-peak live tier.
  - ⚑ **New invariant to honor when doing it (found 2026-07-03):** compose `environment:` outranks `.env` — durable values for compose-set keys (`WEB_SEARCH_ENABLED`, `MODEL_*`) go in the compose env, not `/admin/env` (live PUT works but any reload/restart re-masks it). Detail: `backend/CLAUDE.md` → LLM_BACKEND invariant block.
- `[ ]` **Reasoning trace is pipeline-level, not model chain-of-thought** — the `activity[]` trace in the `done` SSE (grounding badge → "Reasoning steps") shows the pipeline (retrieval/intent/route/budget/model/tools), not the model's internal deliberation. `meta/llama-3.3-70b-instruct` emits no native thinking tokens. Not a defect — closes the practical Dim-3 gap. Real CoT would need either a prompt-based `<thinking>` block (cheap, +tokens/latency, narrated not faithful) or a reasoning-tier model that emits traces (model/cost change). On the home server, a reasoning-capable model (e.g. a future MoE with thinking output) could close this for real. Revisit only if users ask "why did it answer that."

---

## Verification Coverage — residuals (audit 2026-06-22)

> Full audit done: 22 routers + 10 ARQ jobs + 5 crons mapped against `tests/live/` /
> `tests/integration/` / `tests/`. All A–D items (autonomy, scheduler, endpoints, reliability)
> + tools/integrations verified live; 7 bugs found + fixed (BUG-V1–V7 → history note above).
> Runbook: `backend/tests/VERIFICATION_LAUNCH.md`. Only the infra-gated residuals stay open:

- `[~]` **V-B4 / V-E3 Digest email** `[needs-infra]` — `DIGEST_ENABLED=False`, `SMTP_HOST=''`;
  graceful no-op live. Full send path needs SMTP (MailHog).
- `[~]` **V-E1 Real OCR** `[needs-infra]` — `IMAGE_OCR_ENABLED=False`; `paddlepaddle` is a commented
  opt-in (kept out to keep the image lean). Enabling needs the paddle backend installed. Blocks #19.
- `[~]` **V-E2 Notifications dispatch** `[needs-infra]` — no SMTP/VAPID on this stack; email + web-push
  send paths can't run live (mocked in `tests/test_notifications.py`).
- `[ ]` **V-E4 Backup → restore rehearsal** `[needs-infra]` — dump verified; restore over a **staging**
  DB not run (restoring over live is destructive). (Memory-level restore — `POST /admin/memory/restore`
  — IS verified live 2026-07-03; this item is the full pg-dump restore.)
- `[~]` **Real ASR** `[needs-infra]` — `/api/transcribe` ships a stub transcriber (verified live
  2026-07-03: gate + upload + stub text + 503 when off). Real Whisper parked in `QUEUE.md` Q2 (box).

> Re-confirmed 2026-07-03 by the rich full-feature run: all four residuals above remain the only
> infra-gated gaps; everything else on the documented surface verified live
> (`backend/tests/latch/rich_full_logs/rich_full_report.md`).

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
