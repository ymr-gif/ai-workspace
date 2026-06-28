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
> All fixed & verified live.

---

## Open

- `[ ]` **Reasoning trace is pipeline-level, not model chain-of-thought** — the `activity[]` trace in the `done` SSE (grounding badge → "Reasoning steps") shows the pipeline (retrieval/intent/route/budget/model/tools), not the model's internal deliberation. `meta/llama-3.3-70b-instruct` emits no native thinking tokens. Not a defect — closes the practical Dim-3 gap. Real CoT would need either a prompt-based `<thinking>` block (cheap, +tokens/latency, narrated not faithful) or a reasoning-tier model that emits traces (model/cost change). On the home server, a reasoning-capable model (e.g. a future MoE with thinking output) could close this for real. Revisit only if users ask "why did it answer that."

- `[x]` **Drive tools fire on greetings / trivial turns — `drive_list_files` dumped on "ehllo"** (found 2026-06-27; **cold case RESOLVED 2026-06-28 via Task B**; residual = post-latch trivial turns only) — a bare greeting triggers an unprompted full Drive listing. **Evidence:** convo `f1beba8b-…` (admin, 2026-06-27) — `ehllo` then `hello?` each fired `drive_list_files {}` and dumped the whole listing (`tool_call_logs` confirms). **Root cause (confirmed live):** capability-gating injects all 3 Drive schemas whenever the connector is active → `tools` non-empty → llama-8B dropped from the chain (`stream.py:233`) → every turn hits the tool-eager 70B, which calls `drive_list_files` from the schema alone. `select_tool_schemas()` (`registry.py:46`) is a passthrough no-op, so nothing filters tools by message. Regression of old N1 (`91facbe`/`dc18773`), reopened by the de-keyword change (`d3b73a7`). **`_DRIVE_RULES` is NOT causal** — isolation test (rules stripped to empty, rebuilt, `ehllo`) still fired, so prompt-only steering can't carry the fix; the schema itself must be withheld. **Fix — fully specced in `QUEUE.md` → Q3:** Task A (abstention-biased `_DRIVE_RULES`, ships first + its leak rate measured) gates Task B (session-latched semantic gate that removes the schema pre-intent). **Task A SHIPPED + MEASURED 2026-06-28 (root direct, override): leak NOT reduced — abstention rules had zero effect.** Live battery (admin, Drive-active, 5 trials/test, ground-truthed against `tool_call_logs`): T1 `ehllo` **0/5** no-fire, T2 `hello?` **0/5**, T3 real request 5/5 fires (correct), **T4 `thanks` (the critical history-priming case) 0/5** — `drive_list_files {}` fired on every single greeting/ack turn. Confirms the schema, not the prompt, is causal. **→ Task B (schema removal pre-intent) is now MANDATORY, not conditional.** **Task B SHIPPED + verified live 2026-06-28 (root direct, override): the reported cold case is CLOSED.** A session intent latch (`llm/tools/drive_intent.py` — embedding cosine of `query_emb` vs a boot-derived centroid; Redis `drive_latched:{conv_id}`, latch-then-serve same turn; `_drive_gate` = `drive_active AND drive_latched`) withholds the Drive schema until genuine Drive intent appears, so a bare greeting can no longer reach the schema. **Live: `ehllo` (fresh) → latch absent → schema absent → no fire (was 0/5 under Task A); `hello?` no spurious flip; real Drive request flips + fires same turn; second Drive request stays latched + fires.** Threshold 0.60 (e5-tuned, precision-biased; greetings separate cleanly at 0.29–0.39 vs file-requests). **Residual / known weaknesses (NOT the reported bug, tracked open):**
1. **Post-latch history-priming** — `thanks` immediately after a listing still fires (schema is legitimately present once latched; Task A's `_DRIVE_RULES` is the only guard there and stays weak on the 70B).
2. **Session-poisoning via false latch** — the centroid separates greetings cleanly (0.29–0.39) but Drive-intent vs *substantive task/coding imperatives* overlaps (single-centroid cosine ceiling: "help me debug" 0.66, "summarize" 0.61 ≈ weak Drive asks; gate accuracy 32/40). Because the latch is **sticky for 1h**, one false latch on a coding turn flips Drive on for the **rest of the session** → residual #1 then applies to every following turn. Trades the greeting over-fire for a milder session-scoped one. Mitigations to consider: raise `DRIVE_INTENT_THRESHOLD` (0.65–0.70, fewer FPs, more "rephrase needed" misses), make the latch decay/non-sticky, or a 2-class/contrastive gate.
3. **Verification rigor** — T1/T2 are structural (deterministic, schema-absent — firm). T3/T4/T5 are probabilistic 70B behavior and were run **once each**, not the 3–5 repeats the spec asked for; treat those three as suggestive, not statistically settled.

Follow-up options (deferred, record-first, not built): harden `_DRIVE_RULES`, an 8B post-latch pre-pass (Option C), threshold/stickiness tuning. Full record: `HANDOFF.md` → "COMPLETED PHASE: Q3 Task B".

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
