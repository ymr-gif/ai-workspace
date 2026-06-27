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

## Q3 — Drive over-fire fix (abstention rules → conditional semantic latch) — ✅ ACTIONABLE NOW (parked by root direction, NOT hardware-blocked)

- **Status:** runnable today on the NIM stack (Drive-active admin session). Parked here by user
  direction, not blocked. Promote Task A into `HANDOFF.md` → `backend/` when chosen to activate.
- **Owner-to-be:** `backend/` (both tasks) → root (close-out).
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
| `drive_tools.py` | `backend/llm/tools/builtin/drive_tools.py` | `_DRIVE_RULES` L20 · `_drive_gate` L41 (three `should_inject=_drive_gate` regs L65/76/84) |
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

### Task A — Abstention-biased Drive rules

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

### Task B — Session-latched semantic Drive gate (CONDITIONAL on Task A's test-4 measurement)
> Build only if Task A's test-4 pass-rate is unacceptable. Full spec below.

#### Scope
Touches **four files**. Stay inside them:
- `drive_tools.py` — the gate function (`_drive_gate`) and centroid loading
- `stream.py` — thread `query_emb` into the `generate_stream` call (~line 271); inject Drive schemas conditionally on latch
- a new module — `drive_intent.py` (centroid derivation + cosine + phrase store) — keep the logic out of the hot path files
- `registry.py` / wherever `generate_stream` is defined — add the `query_emb` param to the signature

Do **not**: touch routing, the fallback chain, `cache.py`, the RAG retrieval logic itself, or `_DRIVE_RULES` (A owns that — it stays, it covers post-latch).

**First sub-task is the eval set, not the code.** The threshold is unsettable without it. Build the 20/20 labeled set before writing the centroid. If you write the gate first you'll set the threshold by feel — the exact `TOOL_PREFILTER_THRESHOLD=32` sin this whole effort is correcting.

#### Objective
Remove Drive schemas from the model's context until genuine Drive intent appears in the session. Once intent fires, latch the connector in for the rest of the session (binary, name-sorted, cache-stable). Reuse the already-computed `query_emb` — zero new embed calls.

**The guarantee this buys:** before latch, the Drive schema is absent, so the model *cannot* call `drive_list_files` — the "ehllo" cold case becomes structurally impossible, not merely discouraged. After latch, A's abstention rules cover the trivial-turn case. Two windows, two mechanisms.

#### Sub-task B0 — Build the eval set (do this first)
Create `drive_intent_eval.jsonl` (or equivalent), **40 labeled examples**:
- **20 Drive-intent turns** — varied phrasings that should latch: "show my files", "what's in my drive", "pull up that doc about X", "find the budget sheet", "anything in my folders on Y", "open my resume", "do I have a file called…", etc. Vary structure; don't cluster around one verb.
- **20 non-Drive turns** — must NOT latch: "ehllo", "hello?", "thanks", "explain recursion", "what's a hashmap", "help me debug this", "what time is it", "summarize this paragraph" (no file reference), etc. Include the trivial/greeting cases *and* substantive non-Drive questions.

This set does double duty: sets B's threshold **and** measures B's gate accuracy as a number. That number is the portfolio artifact.

#### Sub-task B1 — `drive_intent.py` (centroid + cosine)
```python
# drive_intent.py
import numpy as np
from llm.embeddings import embed_text  # reuse existing embedder

# Persisted phrases — the ONLY place example vocabulary lives.
# Centroid is DERIVED from these at boot, never hardcoded as a vector.
_DRIVE_INTENT_PHRASES = [
    "show my files",
    "what's in my drive",
    "pull up that document",
    "find the file about the budget",
    "open my resume",
    "do I have a file called that",
    "look it up in my documents",
    "what's in my folders",
    "search my drive for the report",
    "list my files",
    "get the spreadsheet from my drive",
    "find my notes on this",
    "open the folder with the photos",
    "what documents do I have",
    "check my drive for it",
    # ~15–20 total, varied
]

_centroid = None

def _build_centroid():
    # CRITICAL: input_type must MATCH the query embed used at request time.
    # helpers.py:241 uses input_type="query". The NIM e5 embedder is
    # ASYMMETRIC — query- and passage-encoded text occupy different
    # subspaces. Embed these phrases as "query" or the cosine ranks wrong
    # while looking plausible.
    vecs = [embed_text(p, input_type="query") for p in _DRIVE_INTENT_PHRASES]
    arr = np.array(vecs, dtype=np.float32)
    c = arr.mean(axis=0)
    c = c / np.linalg.norm(c)  # normalize for cosine via dot product
    return c

def get_centroid():
    global _centroid
    if _centroid is None:
        _centroid = _build_centroid()
    return _centroid

def drive_intent_score(query_emb) -> float:
    if query_emb is None:
        return 0.0  # no signal → fail toward NOT latching (fewer tools)
    q = np.asarray(query_emb, dtype=np.float32)
    q = q / (np.linalg.norm(q) + 1e-8)
    return float(np.dot(q, get_centroid()))

# Set from the 40-example eval set in B0, not by feel.
DRIVE_INTENT_THRESHOLD = 0.0  # PLACEHOLDER — tune against eval set
```

**Build at startup, not lazily on the hot path if you can avoid it** — call `get_centroid()` once at app init so the first request doesn't eat the phrase-embedding cost. If init-time embedding isn't reachable, lazy is acceptable (it's one-time per process), but prefer warm.

#### Sub-task B2 — Thread `query_emb` through
The vector exists at `helpers.py:254` (`query_emb`), spent on RAG, then dropped. `generate_stream` (called at `stream.py:271`) has no access to it.
1. **Add `query_emb` to `generate_stream`'s signature** (default `None` so other callers don't break).
2. **At `stream.py:271`**, pass the already-computed `query_emb` in alongside `retrieved_chunks`.
3. **Confirm `query_emb` is unconditional** at `helpers.py:241`. If there's any path where RAG/embedding is skipped, `query_emb` is `None` on those turns — `drive_intent_score` already handles that by returning 0.0 (fail toward not-latched). Verify the guard; don't assume.

No new embed call. Pure plumbing. Show the signature diff and the call-site diff.

#### Sub-task B3 — Latch + conditional schema injection

**Latch storage — PINNED: Redis, mirroring `drive_listing:{conv_id}`.** (Resolves the spec's
`session.drive_latched` placeholder — there is **no** `session` object in the hot path.) Implement in
`backend/llm/service/stream.py`, the same block that resolves `_drive_active`/`_drive_cache_active` (~L180):
- **Key:** `drive_latched:{conv_id}` — plain string flag (the listing cache is a hash; the latch is just presence).
- **Read** (gate `if _drive_active and conv_id and USE_REDIS`, beside `_drive_cache_active` at L183):
  `_drive_latched = bool(await get_redis().exists(f"drive_latched:{conv_id}"))`.
- **Flip** (same-turn, AFTER `query_emb` is threaded in per B2): if not already latched and
  `drive_intent_score(query_emb) >= DRIVE_INTENT_THRESHOLD` →
  `await get_redis().set(f"drive_latched:{conv_id}", "1", ex=3600)` **and** set `_drive_latched = True`
  in-process so the schema serves THIS turn (latch-then-serve). The score+set must run **before** the
  `ToolContext` / `injected_tools` assembly (L221).
- **TTL = 3600s**, matching `drive_listing`'s `expire(key, 3600)`. Refresh on each latched turn
  (`await get_redis().expire(f"drive_latched:{conv_id}", 3600)`) so an active session stays latched;
  >1h idle → expires → re-latches on the next Drive-intent turn (benign).
- **Thread into `ToolContext`:** add a `drive_latched: bool` field (mirror the existing `drive_cache_active`
  field) set from `_drive_latched`; the gate reads `ctx.drive_latched`.
- **`USE_REDIS` off → no persistence (documented degradation):** `_drive_latched` falls back to the
  same-turn score only — no cross-turn stickiness. Cold case still protected (non-Drive turns score low →
  no tools); the anaphora follow-up ("open that one" after a listing) loses tools until it re-scores.
  Fail toward fewer tools — consistent with `_drive_cache_active` staying False when Redis is off. Do
  **NOT** fall back to capability-only (that reinstates the bug).

**Schema assembly** — the Drive schemas + `_DRIVE_RULES` enter context **iff `ctx.drive_latched`**:
- Currently (`drive_tools.py:41`) `_drive_gate = ctx.drive_active` — capability only. Change the *effective* gate to `ctx.drive_active AND ctx.drive_latched`.
- Before latch: Drive schemas absent, `_DRIVE_RULES` absent. Leading prompt block has no Drive content. Model cannot call a Drive tool.
- After latch: all Drive schemas present, name-sorted (preserve existing sort), `_DRIVE_RULES` present. Block is byte-stable for the rest of the session.

**Cache invariant:** the latch flips **once** per session. One prefix-cache miss on the flip turn, then stable. Do NOT re-evaluate or reorder per turn. Sticky = the schema block is identical across all post-latch turns → prefix cache holds.

**The flip-turn question — decide and document:** when intent fires on turn N, does the Drive schema appear *that same turn* (latch-then-serve, schema available to answer the triggering request immediately) or turn N+1 (next turn)? **Choose latch-then-serve-same-turn** — otherwise the first real Drive request gets a dead turn where the model has no schema to act on. Same-turn means: score → set flag → assemble schemas using the now-true flag → generate. Verify the ordering in the request path puts the latch decision *before* schema assembly.

#### Constraints
- No regex, no keyword matching in code. The latch signal is the embedding cosine — learned, not string-matched. The phrase list is *example sentences for centroid derivation*, not match rules; the embedding generalizes past the exact words.
- Centroid **derived at boot from persisted phrases**, never hardcoded as a vector. (Homeserver bge swap must regenerate it — see migration note.)
- `query_emb is None` → score 0.0 → not latched. Fail toward fewer tools.
- Latch is sticky and per-session. One flip, one cache miss, then stable.
- Do not touch RAG retrieval, routing, fallback chain, or `_DRIVE_RULES` content.

#### Verification
**First: set the threshold (B0 output).** Embed all 40 eval turns as `query`, score each against the centroid. Pick `DRIVE_INTENT_THRESHOLD` as the value that best separates the 20 Drive from the 20 non-Drive. Record: at the chosen threshold, how many of 40 are classified correctly, and which ones miss. **That accuracy number is the deliverable.** If separation is poor (Drive and non-Drive scores overlap heavily), the centroid phrases need revision *before* you trust the gate — report it, don't paper over it.

**Then: behavioral tests** (Drive-active session, check `tool_call_logs`):

| # | Input | Setup | Pass condition | What it proves |
|---|---|---|---|---|
| 1 | `ehllo` | Fresh session | No call — **schema absent**, not just declined | Pre-latch removal works; cold case structurally impossible |
| 2 | `hello?` | After #1, still pre-latch | No call, schema still absent | Latch hasn't spuriously flipped |
| 3 | real Drive request | Triggers latch | Latch flips, schema appears **same turn**, `drive_list_files` fires, names presented | Same-turn serve works; intent detected |
| 4 | `thanks` | Immediately after #3 | No call (schema now present — this is A's job) | Post-latch abstention; A + B division of labor |
| 5 | another real Drive request | Later in same session | Fires normally, **no new cache-disrupting reassembly** | Latch stays put, stable block |

**Test 1 changed meaning from Task A.** In A, passing 1 meant "model declined." In B, passing 1 means "**model couldn't** — schema wasn't there." Verify the *schema absence*, not just the absence of a call. Log or assert that the Drive schemas are not in the assembled tool list pre-latch. That's the structural guarantee; confirm it structurally, don't infer it from behavior.

**Test 4 is still A's territory** — schema is present post-latch, so B doesn't protect this turn. If 4 leaks here and leaked in Task A, that's the documented case for hardening `_DRIVE_RULES` further or considering the 8B pre-pass (Option C) for post-latch turns. But don't pre-build C; record whether 4 is a real problem first.

#### Homeserver migration note — add to the migration doc on build
> Drive intent centroid is embedder-specific. nv-embedqa-e5-v5 and bge-large-en-v1.5 share dimension (1024) but NOT geometry — same phrases embed to different points. On migration: centroid auto-regenerates at boot from `_DRIVE_INTENT_PHRASES` (correct, automatic). BUT `DRIVE_INTENT_THRESHOLD` is tuned to e5's score distribution and will be wrong for bge. **Re-run the 40-example eval set under bge and re-tune the threshold.** Symptom if skipped: latch fires too early/late silently.

Write this down while you understand why. Future-you debugging a mistuned latch won't.

#### Done =
- 40-example eval set built, threshold set from it, gate accuracy recorded.
- `query_emb` threaded, `None`-path confirmed.
- Latch sticky + same-turn serve, schema conditional on latch.
- All 5 behavioral tests run; test 1 verified as *schema-absent* structurally.
- Migration note written.
- Before/after: Task A's test-4 leak rate vs. Task B's test-1 (now structurally clean) — the number that shows what B bought.

Report B0's separation quality first (it's the early kill-signal — bad separation means revise phrases before trusting anything downstream), then the behavioral results.

#### Root implementation notes (adaptation gotchas — not in the original spec)
- **`embed` is async.** `helpers.py:241` does `asyncio.create_task(embed(...))`. B1's `_build_centroid` list-comp (`embed_text(p, …)`) returns coroutines, not vectors — it must `await` each (e.g. `await asyncio.gather(*[embed(p, input_type="query") for p in …])`) inside an async init, or run via `asyncio.run` at a sync boot point. Don't ship the sync list-comp as-is.
- **Symbol name.** The embedder export is `embed` (`llm/embeddings.py`); `helpers.py` imports it as `embed as embed_text`. B1's `from llm.embeddings import embed_text` will ImportError unless aliased — use `from llm.embeddings import embed as embed_text`.
- **`input_type="query"` is correct here (confirmed).** Phrases are example *queries* matched against a live *query* → same encoder side. This is NOT the passage-side case (that's query↔document, e.g. tool-description matching — a different design). Do not "fix" it to passage.
- **`session.drive_latched` storage — DECIDED (Redis).** No `session` object exists in the hot path; latch lives in Redis as `drive_latched:{conv_id}`, mirroring `drive_listing:{conv_id}` (string flag, `set(..., ex=3600)`, read via `exists`, `USE_REDIS`-gated, refreshed per latched turn). Full mechanism + the Redis-off degradation are pinned in B3 above. Rejected a durable `conversations` column: the listing cache it pairs with is already ephemeral Redis (1h), so a durable latch outliving the listing it depends on would desync; matching the existing pattern keeps them consistent.
- **On promote:** cross-post the homeserver migration note into the real migration location (`QUEUE.md` Q1 Recorded + `backend/CLAUDE.md` `LLM_BACKEND` invariant) so it's found during the port, not just here.
