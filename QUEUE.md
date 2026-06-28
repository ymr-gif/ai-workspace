# QUEUE — Deferred / Blocked Backlog

Parked work that is **specced but not in flight** — either blocked on a prerequisite
(currently hardware) or held by root direction. Distinct from `backend/HANDOFF.md` (the active
pipeline). Root parks work here; promotes an entry into `HANDOFF.md` when its blocker clears or
when chosen to activate.

**Rules**
- This file is **root-owned**. Workers do not edit it. Workers only ever touch `HANDOFF.md`.
- Entries here are **not** in flight. Nothing here is being worked.
- To activate an entry: root moves its task list into `HANDOFF.md`, sets the owner, and
  deletes the entry here. Never creates a second `HANDOFF.md`.
- Ordering = priority. Top = next to unblock.

> See `HANDOFF_PROTOCOL.md` → "Queue (deferred work)".
> Decision log: `BUGS.md` → "Decisions — Home-Server Port & #19 Vision".

---

## Q1 — Home-Server Port (Mixtral on llama.cpp) — ⛔ BLOCKED on hardware (2×P40 box)

- **Status:** blocked-on-hardware. Every task that can be built **without** the physical home
  server is **DONE & shipped**; everything remaining needs the 2×P40 box, which does not exist yet.
- **Owner-to-be:** `docker/` (serving) → `backend/` (smoke test) → root (close-out).
- **Flip when the box exists:** set `LLM_BACKEND=homeserver` + `POST /admin/env/reload` (no restart).
- **Decisions:** BUGS.md → "Decisions — Home-Server Port & #19 Vision" (Q-A*/Q-B*).

### Done (no box needed) — shipped
- [x] **Docker serving scaffold** — `llamacpp` + `llamacpp-embed` services (`profiles: [homeserver]`,
  GPU reservation, `--jinja`, `--ctx-size 32768`, q4 KV cache), `docker-compose.homeserver.cpu.yml`
  CPU override, `probe_tool_calls.sh`, `docker/CLAUDE.md` serving section. Validated via `compose config`.
- [x] **tool_calls gate — ✅ PASS (CPU-side, 2026-06-18).** Verdict: llama.cpp emits OpenAI `tool_calls`,
  gated on a tool-aware chat template, **not** the GPU. `--jinja` alone FAILs (bartowski Mistral-7B-v0.3
  ships only the bare `[INST]` template); `--chat-template-file /models/mistral-v3-tool.jinja` flipped it
  to PASS (`get_weather({"city":"Paris"})`). Prompt-based fallback (Q-A2) **not needed** given a tool template.
- [x] **Backend config pre-staged behind inert `LLM_BACKEND`** (`nim`|`homeserver`, default `nim`, 2026-06-19).
  `config.py` gated override repoints endpoints, collapses 3 roles → one Mixtral, sizes ctx 32k, swaps the
  embedder (1024-d, no re-embed), relaxes the `NVIDIA_API_KEY` guard. Hot path (`nim`/`embeddings`/`router`/
  `stream`/`system`) converted to call-time `config.X` so `/admin/env/reload` flips it live (no restart).
  `tests/test_backend_mode.py` 6/6 green.

### Blocked — needs the P40 box (run on the box)
- [ ] Drop Mixtral 8x7B **Q4_K_M** GGUF into `backend/storage/models/`; `docker compose --profile homeserver up -d`.
- [ ] Confirm `/v1/chat/completions` + `/v1/embeddings` reachable from the API container (service DNS `llamacpp`/`llamacpp-embed`).
- [ ] Verify the served Mixtral GGUF's embedded chat template has a tool branch; if not, add `--chat-template-file` (same fix as the CPU override).
- [ ] Measure baseline **TPS** (== SPECTRA Gate 1) before Phase 1B (8x22B).
- [ ] Set `LLM_BACKEND=homeserver` (+ point `HOMESERVER_*` at the LAN services if not the compose-default DNS); `POST /admin/env/reload`.
- [ ] Smoke test against live llama.cpp: chat stream, **tool loop**, file RAG, memory pipeline.
- [ ] `pytest tests/retrieval/test_hybrid_eval.py tests/test_drive.py tests/test_calendar.py -v` stays green.
- [ ] Close-out: update model tables in `backend/CLAUDE.md`, root `CLAUDE.md`, `SUMMARY.md`; fill **Recorded** below.

### needs-root (on close-out — root handles)
- [ ] `.env` / `.env.example`: endpoint + model vars (`NIM_URL`, `NIM_EMBEDDING_URL`, `MODEL_*`,
  `EMBEDDING_DIM`, `NVIDIA_API_KEY` optionality). `ROADMAP.md` deployment note.

### Recorded (work already banked)
- Services: `llamacpp` (:8080, chat) + `llamacpp-embed` (:8081, embed), image `ghcr.io/ggml-org/llama.cpp:server-cuda`, `profiles: [homeserver]`.
- Endpoints (when up): `NIM_URL=http://llamacpp:8080/v1/chat/completions`, `NIM_EMBEDDING_URL=http://llamacpp-embed:8081/v1/embeddings`.
- Weights: bind mount `backend/storage/models/ → /models:ro`; filenames via env (`LLAMACPP_MODEL`, `EMBED_MODEL`; + `LLAMACPP_CTX`, `LLAMACPP_NGL`, `LLAMACPP_PARALLEL`, `EMBED_POOLING`, `EMBED_NGL`).
- Chat flags: `--jinja`, `--ctx-size 32768`, `--cache-type-k/v q4_0`, `--flash-attn`, `--n-gpu-layers 999`, `--parallel 2`. Embed flags: `--embeddings`, `--pooling cls` (bge), `--ctx-size 512`. Keeps 1024-d → no re-embed.
- tool_calls gate (2026-06-18, CPU): `ghcr.io/ggml-org/llama.cpp:server`, `mistral-7b-instruct-v0.3.Q4_K_M.gguf`, ctx 8192. Run 1 (`--jinja` only) → FAIL (prose; `/props` = 470-char bare `[INST]`, no tool branch). Run 2 (+ `--chat-template-file /models/mistral-v3-tool.jinja`) → PASS. CPU warmup ~4.5 min → use `WAIT=360` / healthcheck `start_period`.
- Backend config (2026-06-19): inert `LLM_BACKEND` flag; flips endpoints / model-collapse / ctx-32k / embedder / guard live via `/admin/env/reload`. See `backend/CLAUDE.md` → `LLM_BACKEND` invariant.
- Files touched: `docker/docker-compose.yml`, `docker/docker-compose.homeserver.cpu.yml` (new), `docker/probe_tool_calls.sh` (new), `docker/CLAUDE.md`, `backend/config.py` + call-time consumers (`nim.py`/`embeddings.py`/`router.py`/`service/stream.py`/`api/system.py`), `backend/tests/test_backend_mode.py` (new), `.env.example`.
- **To fill on the box:** served model id, context window confirmed, tool_calls verdict (live), re-embed avoided, TPS baseline.
- **Connector-intent latch re-tune (Q3 Task B, cross-posted):** `llm/tools/connector_intent.py`'s
  per-connector centroids (drive/calendar/gmail) auto-regenerate at boot under bge, but `INTENT_THRESHOLDS`
  (drive 0.60 / calendar 0.60 / gmail 0.65) are tuned to nv-embedqa-e5-v5's score geometry and are
  **wrong for bge-large-en-v1.5**. On the swap: re-run `tests/{drive,calendar,gmail}_intent_eval.jsonl`
  under bge, re-set all three thresholds, and recheck cross-talk (the single-winner margin shifts too).
  Symptom if skipped: connector schemas latch too early/late silently. (Also in `backend/CLAUDE.md` →
  LLM_BACKEND invariant.)

### Verification (final, on the box)
1. API container reaches llama.cpp `/v1/chat/completions` + `/v1/embeddings`.
2. Chat streams; agent tool loop fires a real `tool_call` (or documented prompt-fallback).
3. File RAG + memory pipeline work with 1024-d `bge-large-en-v1.5` — no re-embed.
4. Budget allocator sizes to 32k (no oversized-context truncation errors).
5. `pytest` retrieval + drive + calendar suites green.

---

## Q2 — #20 Voice Input: real ASR transcription — ⛔ BLOCKED on hardware (home-server box)

- **Status:** blocked-on-hardware. The **endpoint + stub transcriber + frontend mic** ship now via
  `HANDOFF.md` Phase 1 (text-path proven end-to-end with a stub). This entry is the **real Whisper**
  swap-in that replaces the stub once the box (or a dev GPU) exists. STT only — TTS reply out of scope.
- **Owner-to-be:** `backend/` (transcriber impl) → root (close-out: `.env.example`, deps note).
- **Promote when:** the home-server box exists, OR you want CPU dev transcription sooner (faster-whisper
  `tiny.en`/`base.en` runs on CPU — see "dev shortcut" below).

### The contract the stub already satisfies (do NOT change — real impl must match)
- **Module:** `backend/services/transcribe.py`
  - `async def transcribe_audio(data: bytes, mime_type: str, *, language: str | None = None) -> str`
  - Returns plain transcript text (`""` on no speech). Never raises to the caller — log + return `""`
    on decode/model error (mirror the processor extractor contract).
  - Dispatch on `config.ASR_BACKEND`: `"stub"` (Phase 1, returns the placeholder) → add `"faster_whisper"` here.
  - CPU/GPU work wrapped in `asyncio.to_thread()` (same rule as `processor.py`).
- **Endpoint (unchanged):** `POST /api/transcribe`, JWT-auth, multipart `file`, gated by `VOICE_ENABLED`
  (503 when off). Response `{"text": str, "backend": str, "stub": bool}` — real impl flips `stub:false`.
- **Config keys (Phase 1 adds; real impl consumes):** `VOICE_ENABLED` (bool, default false),
  `ASR_BACKEND` (str, default `"stub"`), `ASR_MODEL` (str, default `"base.en"`), `ASR_LANGUAGE` (str, optional).

### Real-impl to-do (on promote)
- [ ] Add `faster-whisper` to `backend/requirements.txt`; implement the `"faster_whisper"` branch
  (lazy import + module-level model cache keyed on `ASR_MODEL`; `compute_type="int8"` CPU / `"float16"` GPU).
- [ ] **Audio decode gap:** `MediaRecorder` emits **webm/opus** (or mp4/aac on Safari). faster-whisper needs
  PCM/wav or a file path it can `ffmpeg`-decode → **`ffmpeg` system binary required in the API image**
  (docker/ change — apt `ffmpeg`). Confirm before coding; alternative is `av`/`soundfile` pip decode. **This
  is the one needs-docker item.**
- [ ] Language: pass `ASR_LANGUAGE` through; default auto-detect if unset.
- [ ] Tests: real branch behind a mock (no model weights in CI) — assert dispatch + to_thread + error→"".
- [ ] needs-root close-out: document `VOICE_ENABLED`/`ASR_*` in `.env.example`; note `ffmpeg` dep + the
  faster-whisper model download in `docker/CLAUDE.md`; tick nothing in ROADMAP (already ticked at Phase 1 ship).

### dev shortcut (optional, no box)
- faster-whisper `tiny.en`/`base.en` int8 transcribes on CPU in ~real-time for short clips — you can promote
  this entry **before** the box purely to get working voice in dev; only the GPU speed-up waits on hardware.

### Recorded (fill on impl)
- _(chosen model + compute_type; webm decode path taken — ffmpeg vs pip; measured latency)_

---

## Q3 — Drive over-fire fix (abstention rules → semantic latch) — ✅ DONE (Task A + Task B shipped 2026-06-28)

- **Status:** **DONE.** Task A (abstention `_DRIVE_RULES`) shipped but measured ineffective (test-4 0/5).
  **Task B (session-latched semantic Drive gate) shipped + verified live 2026-06-28 (root direct, override):**
  Drive schema is withheld until an embedding-cosine intent latch fires, so the cold "ehllo" over-fire is
  now **structurally impossible** (schema absent pre-latch) — confirmed live (T1 no-fire/latch-absent vs
  Task A's 0/5). Latch-then-serve same turn; sticky Redis `drive_latched:{conv_id}`. Residual: post-latch
  trivial-turn leak ("thanks" after a listing) stays — Task A's territory, Option C (8B pre-pass) deferred
  record-first. Full record: `HANDOFF.md` → "COMPLETED PHASE: Q3 Task B" + History. Bug `BUGS.md` "Drive
  fires on greetings" → cold case closed.
- **Owner:** done (root). Task A + Task B both merged.

> **Task A measurement (2026-06-28, admin Drive-active, 5 trials/test, ground-truthed vs
> `tool_call_logs`):** T1 `ehllo` 0/5 no-fire · T2 `hello?` 0/5 · T3 real request 5/5 fires (correct) ·
> **T4 `thanks` 0/5** (the history-priming case). The 70B calls `drive_list_files {}` on every turn
> while the schema is present — abstention prompt text had **zero** effect. This is the before-baseline
> Task B must beat: T1 must become *structurally* 0-fire (schema absent), not merely discouraged.
- **Bug:** BUGS.md → Open → "Drive tools fire on greetings / trivial turns — `drive_list_files`
  dumped on 'ehllo'". Root cause confirmed live (2026-06-27): capability-gate injects Drive schemas →
  `tools` non-empty → llama-8B dropped → tool-eager 70B calls `drive_list_files` from the schema alone.
  `_DRIVE_RULES` is NOT causal (isolation test: stripped → still fired). Rules are the post-schema
  mitigation lever, nothing more.
- **Sequencing:** Task A ships first and is measured. **Task B is conditional on Task A's Test-4
  pass-rate** (see Done). Do not start B until A's test 4 is measured over multiple runs.

### Cold-start file map (resolve the bare filenames below to THESE; line nums = 2026-06-28 snapshot, re-anchor via graphify before editing)
| Spec says | Actual file | Role / anchor |
|---|---|---|
| `drive_tools.py` | `backend/llm/tools/builtin/drive_tools.py` | `_DRIVE_RULES` L20 (now abstention text, ~L20–54 after Task A) · `_drive_gate` **L56** (three `should_inject=_drive_gate` regs **L80/91/99**) |
| `stream.py` (define / assemble) | `backend/llm/service/stream.py` | `generate_stream` def **L92** (B2 signature) · `injected_tools` assembly **L221** · `_rules_block` injection **L281–287** (B3) |
| `stream.py` (call site) | `backend/api/chat/stream.py` | `service.generate_stream(` call **L271** (B2-step2 — pass `query_emb` here) |
| `helpers.py` | `backend/api/chat/helpers.py` | `query_emb` produced **L254** (`embed` task fired L241); used by RAG L259+ |
| `registry.py` | `backend/llm/tools/registry.py` | `select_tool_schemas`/`run_tool` only — **`generate_stream` is NOT here.** The Scope line "registry.py / wherever generate_stream is defined" is misleading: the signature edit is in `llm/service/stream.py:92`. Touch `registry.py` only if you route the latch through `select_tool_schemas`; otherwise skip it. |

> ⚠ Two different `stream.py` files. `llm/service/stream.py` = the engine (define + assemble); `api/chat/stream.py` = the HTTP caller (call site). There is also `api/files/stream.py` — unrelated, do not touch. Graphify-first mandate applies (re-locate every anchor with `graphify query`/`explain` before editing; lines drift).

### Verification runbook (both tasks) — how to actually run the behavioral tests
- **Stack must be up** (`docker ps` → `docker-api-1` healthy on :8000). Code is baked into the image (no bind-mount, no `--reload`) → after any backend edit, rebuild: `cd docker && docker compose -f docker-compose.yml up -d --build api` (+ verify health 200). See `backend/tests/VERIFICATION_LAUNCH.md` + `tests/VERIFICATION.md`.
- **Login (admin, Drive-active):** `POST /auth/token` form-encoded `username=admin&password=admin-secret` → `access_token`.
- **Send a turn:** `POST /chat/stream` `Authorization: Bearer <tok>`, JSON `{"message":"ehllo"}` (omit `conversation_id` to start fresh; reuse the `done` event's `conversation_id` to continue a session).
- **Check the result:** `psql -U scylla -d nimrouter` (in `docker-postgres-1`) → `SELECT tool_name,args FROM tool_call_logs WHERE conversation_id='<id>'`. Or read the SSE `tool_call` event / `model_call → requested tool(s)` status line.
- **⚠ Cleanup after (pollution):** these run under admin and pollute history + prime the 70B. Delete each test conversation when done: `DELETE FROM conversations WHERE id='<id>'` — note `tool_call_logs.conversation_id` is `ON DELETE SET NULL`, so also clear the orphaned rows (`DELETE FROM tool_call_logs WHERE conversation_id IS NULL AND created_at > now()-interval '15 min'`).

---

### Task A — Abstention-biased Drive rules — ✅ DONE 2026-06-28 (shipped; measured ineffective)

> **Outcome:** `_DRIVE_RULES` rewritten to abstention-biased text (`backend/llm/tools/builtin/drive_tools.py`,
> one symbol; `_POST_LISTING`/`_drive_gate`/registrations untouched), image rebuilt, `graphify update .` run.
> **Behavioral battery (5 trials/test, ground-truthed vs `tool_call_logs`): T1 0/5, T2 0/5, T3 5/5, T4 0/5.**
> Zero reduction in spurious fires — confirms prompt steering cannot carry this fix; schema must be withheld.
> Test conversations cleaned up post-run. Bug stays open (BUGS.md). → Task B mandatory.

#### Scope
Touch **one file**: `drive_tools.py`. Edit **one symbol**: `_DRIVE_RULES` (line ~20). Nothing else.
Do not touch `stream.py`, `registry.py`, `generate_stream`, routing, or gating. This task is text-only.

#### Objective
Replace the flow-describing `_DRIVE_RULES` block with abstention-biased, condition-gated instruction.
Reduce spurious Drive-tool calls on non-Drive turns (greetings, questions, chat) without removing the
schema or changing routing.

**This is a probabilistic mitigation, not a guarantee.** It covers the post-latch window where the
schema is present. It will reduce, not eliminate, spurious fires on the NIM 70B. Do not claim it closes
the bug. Measure the residual leak — that measurement justifies Task B.

#### The change
**File:** `drive_tools.py`, symbol `_DRIVE_RULES` (~line 20). **Replace the entire block with:**

```python
_DRIVE_RULES = """\
## Google Drive access

You have Google Drive tools available this session. Having access does
not mean you should use it. On most turns you should not.

Call a Drive tool ONLY when the user's CURRENT message refers to their
own files, documents, folders, or Drive contents — explicitly or by
clear implication (asking what they have, to open or find a document,
to look something up in their files).

Do NOT call any Drive tool for:
- greetings, small talk, or acknowledgements ("hi", "hello?", "thanks")
- general questions you can answer directly
- coding help, explanations, or discussion
- any turn where the user has not pointed at their own files

Base the decision on the user's CURRENT message only. A previous file
listing in the conversation is not a reason to call again.

When unsure whether a turn needs Drive, do not call it — answer
directly. A wrong file listing is worse than a missing one; the user
can always ask.

When you DO call drive_list_files and results return, present the file
names concisely and stop.
"""
```

**If the original had leading/trailing structure** (markdown fences, surrounding keys, concatenation
with other rule blocks), preserve that wrapper exactly — change only the inner text. Show the
before/after of the full symbol including any wrapper.

#### Why each clause exists (do not edit these out as "redundant")
| Clause | Targets |
|---|---|
| "Having access does not mean you should use it. On most turns you should not." | The access→use false inference — the root of every spurious fire |
| "ONLY when the user's CURRENT message refers to…" | Capability-only gating; ties the trigger to *this turn's* content |
| "Base the decision on the user's CURRENT message only. A previous file listing is not a reason to call again." | History-priming / the turn-2 self-reinforcement loop |
| Explicit don't-call list | The "ehllo"/"hello?" failure verbatim |
| "When unsure, do not call. A wrong listing is worse than a missing one." | Asymmetric bias toward abstention on borderline turns |
| "When you DO call… present concisely and stop." | Preserves intended UX, gated behind an actual call instead of priming one |

#### Constraints
- No regex, no keyword matching, no vocabulary lists in code. Gating is intent-condition language in the prompt only.
- Do not add a default `system_prompt`. Do not change `_drive_gate`. Do not alter the fallback chain or model routing.
- Do not modify the schema descriptions in this task.
- Output: full before/after of `_DRIVE_RULES` including any wrapper, and confirmation no other lines in the file changed.

#### Verification — run all four, record results
Use a Drive-active session (admin). Record whether `drive_list_files` fires (check `tool_call_logs`).

| # | Input | Setup | Pass condition |
|---|---|---|---|
| 1 | `ehllo` | Fresh session | No `drive_list_files` call |
| 2 | `hello?` | Same session, after #1 | No `drive_list_files` call |
| 3 | a real Drive request (e.g. "what files do I have?") | Fresh or continued | `drive_list_files` fires, names presented |
| 4 | `thanks` | **Immediately after #3's listing** | No `drive_list_files` call |

**Test 4 is the one that matters.** It's the history-priming case — the schema is present *and* a prior
listing sits in context. If A holds here, the "CURRENT message only" language is working. If 4 re-fires,
A lost to history-priming and Task B's pre-intent removal is mandatory, not optional.

**Tests 1–2 passing is necessary but not sufficient.** They're the easy case. Do not ship on 1–2 alone.

#### Expected outcome (honest)
- 1–3 likely pass.
- 4 is the coin-toss — this is where the NIM 70B's probabilistic abstention shows. Given the three prior
  leaks of this mechanism (`write_memory`, `list_files`, this bug), expect 4 to be unreliable across runs.
- **Record 4's result across ~3–5 repeated runs**, not once. A single pass on 4 isn't proof on a
  probabilistic model. The pass *rate* on 4 is your baseline spurious-fire number and the documented
  justification for B.

#### Done =
A merged, all four tests run, test-4 pass-rate recorded over multiple runs. That number carries into
Task B as the before-baseline. **Do not start B until test 4's behavior is measured.**

---

> **Task B** (session-latched semantic Drive gate) was promoted into `backend/HANDOFF.md` on
> 2026-06-28 and is **in flight** — its full spec (B0 eval set → B1 `drive_intent.py` centroid →
> B2 `query_emb` threading → B3 Redis latch + gate flip) lives there now, not here. The Q3 header
> above + the shared file map / verification runbook remain as the reference it was cut from.
