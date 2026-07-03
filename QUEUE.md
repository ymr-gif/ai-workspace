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

> History note (closed entries removed once shipped — see git log of this file):
> **Q3 Drive over-fire fix** DONE 2026-06-28 — Task A (abstention `_DRIVE_RULES`) shipped, measured
> ineffective (T4 0/5); Task B (session-latched semantic gate) shipped + verified live, cold over-fire
> structurally impossible. Full record: `HANDOFF.md` → "COMPLETED PHASE: Q3 Task B"; Task-A spec, file
> map + verification runbook preserved in this file's git history (removed 2026-07-03).

---

## Q4 — Stateless-chat spend metering — ✅ READY (no blocker; promote to `backend/HANDOFF.md`)

- **Status:** ready-to-activate. Bug: `BUGS.md` → Open → "Stateless chat endpoints: spend is unmetered".
- **Owner-to-be:** `backend/`.
- **Tasks:**
  - [ ] Add `_check_cost_cap` pre-flight to `POST /v1/chat/completions` (`api/compat.py`) — mirror `49cb6ea`.
  - [ ] Record tokens + cost on nonstream `/chat` AND `/v1/chat/completions` — mirror the calc in
    `api/chat/background.py`; a usage-ledger write suffices (no conversation/message persistence).
  - [ ] Tests: capped user → 402 on compat; nonstream turn accrues to the rolling window (mock NIM).
  - [ ] Live verify: one nonstream turn → `GET /usage` delta > 0.
- **Files:** `api/compat.py`, `api/chat/router.py`, `api/chat/helpers.py:_check_cost_cap` (reuse),
  `api/chat/background.py` (reference calc).

---

## Q5 — Close the needs-infra residuals (email · push · restore rehearsal) — ✅ READY (no hardware)

- **Status:** ready. From `BUGS.md` → residuals; identified fixable-now by the 2026-07-03 rich-full run.
- **Owners:** mixed — docker (MailHog service) → backend/root (triggers + verification).
- **Tasks:**
  - [ ] **V-E4 pg-restore rehearsal** (root ops, ~15 min): scratch postgres container ← latest
    `storage/backups/` dump; verify table count + spot rows; record in `VERIFICATION_LAUNCH.md`, tick V-E4.
  - [ ] **V-B4/E3 digest email** (docker + root): MailHog service behind `profiles: [mail]`;
    `SMTP_HOST=mailhog`, `DIGEST_ENABLED=true` → trigger digest → email visible in MailHog UI.
  - [ ] **V-E2 web push** (backend/root): generate VAPID keypair, set env → localhost browser test
    (secure context works on localhost, no TLS needed) → push received.
- ⚑ Compose-env precedence applies when flipping these flags (`backend/CLAUDE.md` → LLM_BACKEND invariant).

---

## Q1 — Home-Server Port (Mixtral on llama.cpp) — ⛔ BLOCKED on hardware (2×P40 box)

- **Status:** blocked-on-hardware. Every task that can be built **without** the physical home
  server is **DONE & shipped**; everything remaining needs the 2×P40 box, which does not exist yet.
- **Owner-to-be:** `docker/` (serving) → `backend/` (smoke test) → root (close-out).
- **Flip when the box exists:** set `LLM_BACKEND=homeserver` + `POST /admin/env/reload` (no restart).
- **Decisions:** BUGS.md → "Decisions — Home-Server Port & #19 Vision" (Q-A*/Q-B*).

### Done (no box needed) — shipped; operational detail banked in "Recorded" below
- [x] Docker serving scaffold (`llamacpp` + `llamacpp-embed`, CPU override, `probe_tool_calls.sh`) — validated via `compose config`.
- [x] tool_calls gate — PASS CPU-side 2026-06-18; needs a tool-aware `--chat-template-file` (`--jinja` alone insufficient).
- [x] Backend pre-staged behind inert `LLM_BACKEND` — live-flippable via `/admin/env/reload`; `test_backend_mode.py` 6/6.

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
- **Connector-intent latch re-tune (Q3 Task B, cross-posted) — MOOT WHILE STUBBED:** Drive/Calendar/Gmail are UI-stubs (`ENABLED_CONNECTOR_TYPES = []`); the latch never fires. If connectors are re-enabled AND the home-server bge swap is done, then: `llm/tools/connector_intent.py`'s per-connector centroids (drive/calendar/gmail) auto-regenerate at boot under bge, but `INTENT_THRESHOLDS` (drive 0.60 / calendar 0.60 / gmail 0.65) and `FLOOR_THRESHOLD` (0.65) are tuned to nv-embedqa-e5-v5's score geometry and are **wrong for bge-large-en-v1.5**. On the swap: re-run `tests/{drive,calendar,gmail}_intent_eval.jsonl` under bge, re-set all three per-connector thresholds + floor threshold, and recheck cross-talk (the single-winner margin shifts too). Symptom if skipped: connector schemas latch too early/late silently. (Also in `backend/CLAUDE.md` → LLM_BACKEND invariant.)

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
