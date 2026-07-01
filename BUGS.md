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
> **2026-06-28 (post-latch): Drive/Calendar/Gmail moved to UI stubs** (`ENABLED_CONNECTOR_TYPES = []`). The latch code (`connector_intent.py`) is now harmless dead code — no active connectors can exist, so it never fires.

---

## Open

- `[x]` **`write_memory` fires on greetings / trivial turns → empty reply + spurious "save to memory?" card + memory pollution** (found 2026-06-28, live; **FIXED + verified 2026-06-28**, root override)
  - **Symptom:** on a bare greeting the 70B calls `write_memory` to store a useless "fact" (e.g. *"The user is saying hello"*). `write_memory` returns a confirm-sentinel that **pauses** the tool loop, so the assistant message is saved **empty** — the user sees a blank bubble + a "save to memory?" confirm card instead of a reply, and memory accrues junk facts.
  - **Evidence (live, with the connector latch already shipped):** conv `a863dcbf-da40-45bd-ad43-e5a7d0bf7e92` (admin, 2026-06-28 08:02) — three trivial turns, each empty assistant + a `write_memory` call: `hello?`→`{"fact":"The user greeted the AI for assistance."}`, `hello?`→`{"fact":"The user is saying hello"}`, `what is up?`→`{"fact":"The user is greeting and asking what is up."}`. Contrast conv `b8aa2abd` `hello`→clean reply, no tool.
  - **Non-deterministic:** a fresh `hello?` repro routed to the **8B** (`route` reason `router`) → clean reply, no tool. It only misfires when the **70B** happens to be selected for the trivial turn (the router is probabilistic; history-priming from prior greetings nudges it).
  - **Root cause:** `write_memory`'s gate `_inject_write_memory(ctx)` (`backend/llm/tools/builtin/memory_tools.py:27`) = `ctx.db is not None and ctx.is_reasoning` — **capability only** (offered whenever the 70B reasoning model is chosen), with **no intent gate** (unlike the connector tools, now latch-gated). So any trivial turn that lands on the 70B (router / `_needs_memory_tool` `backend/llm/service/context.py:42` / `intent=="task"` branch in `llm/service/stream.py`) gets `write_memory` in context, and the tool-eager 70B fires it from the schema alone. **Same over-fire class as the Drive/connector bug, but for a non-connector tool** — and now the most visible greeting over-fire since the connectors were latch-gated.
  - **Empty-reply mechanism:** `_exec_write_memory` (`memory_tools.py:31`) returns the `CONFIRM_WRITE_PREFIX` sentinel → SSE `confirm_write_memory` → the tool loop pauses for user confirmation (mirrors `ask_user` / calendar-write), ending the turn with **no assistant text** (the confirm branch in `api/chat/stream.py` saves no content). Two facets: (a) over-fire on trivial turns; (b) even a *legitimate* `write_memory` should still emit a short text reply, not an empty bubble.
  - **Prior mitigation insufficient:** `d3b73a7` (2026-06-23) already hardened the `write_memory` schema description to "RARE action" to curb exactly this — it still fires. Same lesson as Drive Task A: prompt/schema steering can't carry it on the tool-eager 70B; the tool must be **withheld** until genuine memory intent, or made non-blocking.
  - **Fix SHIPPED 2026-06-28 (root override):** `_inject_write_memory` (`memory_tools.py:27`) now gates on `db AND is_reasoning AND _needs_memory_tool(message)` — the tool is offered only on a reasoning turn with **explicit** memory-write intent ("remember"/"memorize", or a write-verb + "memory"; the same deterministic keyword signal that already routes memory turns to the 70B), so greetings/questions/coding never inject it. **Embedding-cosine memory-intent was tried first and rejected — measured too weak to separate** (live 40-example eval: best 30/40; greetings `hello?`/`thanks` ~0.58 sit *inside* the real-memory range, and "summarize this paragraph" scored 0.75 > most memory statements), so adding it (OR-style) would only have leaked task-imperatives. Implicit preferences are **still captured** by the background memory-extraction pipeline (`summarizer/memory.py`); `write_memory` is just the explicit immediate confirm-card path, so explicit-only gating loses nothing. **Verified:** unit `tests/test_write_memory_gate.py` (greetings/summarize/debug → not injected; "remember …" → injected; needs reasoning + db) + live (`hello?` ×N → no `write_memory`, clean reply). **Residual not addressed:** facet (b) — a *legitimate* `write_memory` still ends the turn with an empty assistant bubble + the confirm card (acceptable, mirrors the calendar-write confirm UX); revisit only if the empty bubble bothers users.
  - **Repro (before fix):** send `hello?` repeatedly under admin; when a turn routes to the 70B (watch the `route` SSE / `route_reason`), `write_memory` fires and the saved `messages.content` is empty (confirm via `tool_call_logs`). Delete the test conversation after — it pollutes history + memory.
- `[~]` **Connector intent-latch — residual leaks (Drive / Calendar / Gmail)** — **MOOT (2026-06-28):** connectors are UI-stubbed (`ENABLED_CONNECTOR_TYPES = []`), the latch never fires. Re-open if re-enabled. Original detail: the latch makes the *cold* greeting case structurally impossible, but three weaknesses remain: **(1) post-latch trivial turns** — once a connector is latched, `thanks`/`ok` can still fire its tools (schema legitimately present; the per-connector `_RULES` prompt is the only guard and stays weak on the 70B). **(2) sticky-latch session-poisoning** — the latch is sticky 1h and the centroid can't cleanly separate connector-intent from *substantive task/coding imperatives* ("help me debug" ≈ 0.66 vs the drive centroid; gate accuracy ~32/40), so a false latch on a coding turn flips a connector on for the rest of the session (single-winner caps the blast radius at **one** connector, not all three). Mitigation: `FLOOR_THRESHOLD` (0.65) added 2026-06-29 — rejects weak winners that only "won" because every score was low ("help me debug" at ~0.66 clears per-connector drive 0.60 but NOT the floor 0.65, so no latch). The floor complements the per-connector thresholds; the full condition is `scores[winner] >= max(INTENT_THRESHOLDS[winner], FLOOR_THRESHOLD)`. Other mitigations considered (decay latch, 2-class gate, 8B pre-pass) deferred. **(3) verification rigor** — the cold-case tests are structural/deterministic (firm), but the probabilistic 70B behavioral tests were run once each, not the 3–5 repeats originally specced. Shipped record: `HANDOFF.md` → "COMPLETED PHASE: Q3 Task B" + the two 2026-06-28 History rows.
- `[ ]` **Connector latch can't separate terse-genuine from terse-vague — no clean threshold (over-fire vs under-fire)** (data-confirmed 2026-07-01)
  - **Symptom:** the embedding-cosine latch conflates genuine terse requests ("read that file", "any new mail") with connector-adjacent vague turns ("find my things", "check my stuff"). Any single floor either over-fires on vague or under-fires on genuine — the bands overlap.
  - **Evidence (offline A/B, 150 weak_real + 150 none_intent, same embeds; `backend/tests/latch/RUNLOG.md` 2026-07-01):** weak_real median 0.61 (mean) / 0.66 (nearest-example); none_intent reaches 0.71–0.77. Gap p10(weak) vs p90(none) = **−0.196 (mean) → −0.159 (nearest-example)** — still no separation. At floor 0.65 the new scoring over-fires 61% of vague; at 0.70, over-fire 15% / genuine recall 28%.
  - **Root cause:** the embedder (`nv-embedqa-e5-v5`) does not linearly separate these short phrasings — a representational limit, not a scoring bug. Same wall the `write_memory` gate hit (embedding "too weak to separate" → fell back to keywords; see that entry above).
  - **Files:** `backend/llm/tools/connector_intent.py` (`intent_score`, `INTENT_PHRASES`, `INTENT_THRESHOLDS`, `FLOOR_THRESHOLD`); `backend/llm/service/stream.py:_resolve_connector_latches` (gate/flip); abstention rules `_DRIVE_RULES`/`_CALENDAR_RULES`/`_GMAIL_RULES` in `backend/llm/tools/builtin/{drive,calendar,gmail}_tools.py`; harness `backend/tests/latch/`.
  - **Done so far:** mean-centroid → nearest-example (max over phrase embeddings) + terse anchors (`c3b020d`) — lifted genuine recall but lifted vague ~equally (marginal). Recalibrated FLOOR 0.65→0.70 (`194b335`), precision-biased (over-fire 37%→15%, sheds recall).
  - **Solutions / how to improve (ranked):**
    1. **Clarify fallback (primary next).** Accept under-fire on vague; the model asks "which document/calendar/inbox?" so the user's next turn scores clean. **CRITICAL GAP found 2026-07-01:** the `_{connector}_RULES` (which hold the "ask which file(s)" nudge, e.g. `drive_tools.py:_POST_LISTING`) are attached as `behavioral_rules` **on the tools**, so they are injected **only when the connector is LATCHED** — i.e. absent on the under-fire turn where we need them. Fix: inject a lightweight, always-present-when-a-connector-is-active one-line clarify nudge ("user has Drive/Calendar/Gmail connected; if a short/ambiguous message seems to want their files/schedule/mail but you're unsure which, ask them to clarify instead of guessing"), independent of the schemas (keeps schemas withheld + KV-cache stable), then verify the model actually asks.
    2. **Hybrid explicit signal (memory-write precedent).** OR the semantic score with a cheap deterministic cue — possessive + connector-noun ("my file/document/spreadsheet"→drive; "my calendar/schedule/meeting"→calendar; "my email/inbox/mail"→gmail). Deterministic latch for the unambiguous cases, semantic for the rest; mirrors `_needs_memory_tool` (`context.py:42`).
    3. **Threshold re-tune with balanced volume** — the 0.70 floor is provisional (one 150/150 sample).
    4. **bge re-tune** — the home-server embedder swap changes geometry; re-measure (may separate differently).
    5. Deferred alternatives: decay latch, 2-class gate, 8B pre-pass.
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
  DB not run (restoring over live is destructive).

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
