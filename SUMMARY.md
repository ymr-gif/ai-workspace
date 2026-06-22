# NIM AI Gateway — Project Summary

Updated: 2026-06-22

---

## What This Is

FastAPI backend routing chat messages to NVIDIA NIM models via keyword classification.
React/Vite frontend. Docker Compose stack: Postgres + pgvector, Redis, Neo4j, Prometheus, Grafana.

**Vision:** A multi-user AI system where each person has a private, continuously evolving digital mind
that unifies memory, reasoning, and future autonomous intelligence into one personalized cognitive workspace.

---

## Deployment Direction (planned 2026-06-17)

> The NVIDIA NIM models below are a **test backend only**. The project is being ported to a
> **self-hosted home AI server** — one OpenAI-compatible endpoint, so porting = repoint env vars.

- **Runtime:** llama.cpp / GGUF (Pascal P40 GPUs). Verify Mixtral `tool_calls` work first — the agent loop depends on it.
- **Chat model:** Mixtral 8x7B (Phase 1A, 2×P40) → 8x22B (Phase 1B, 4×P40) → eventual ~145B MoE (prefer vision-native). **Text-only.**
- **Context:** 32k (Mixtral trained limit) — `CONTEXT_WINDOWS` must reflect this, not 131072.
- **Embedder:** stay 1024-d (`bge-large-en-v1.5`) to avoid a full re-embed.
- **Vision / #19:** chat is text-only → image OCR runs on **CPU (PaddleOCR)**, gated `IMAGE_OCR_ENABLED` (default false); both Library-upload and chat `image_b64` paste route through OCR → text.
- Full decision log: `BUGS.md` → "Decisions — Home-Server Port & #19 Vision". Sibling projects: SPECTRA (inference middleware) + HALO (speculative decoding) share the GPU box.

---

## Repo Layout

```
ai-api/
├── .env                    ← secrets (gitignored); loaded by find_dotenv()
├── .env.example            ← all supported vars documented
├── CLAUDE.md               ← root project reference
├── ROADMAP.md              ← vision, backlog, implementation order
├── COMMANDS.md             ← common dev commands
├── BUGS.md                 ← bug tracker + home-server design decisions
├── HANDOFF_PROTOCOL.md     ← multi-agent delegation workflow
├── HANDOFF.md              ← current owner file (exactly one at all times)
├── QUEUE.md                ← deferred/planned features backlog (root-owned)
├── HANDOFF_ARCHIVE.md      ← completed handoff records
├── SUMMARY.md              ← this file
├── backend/                ← FastAPI app
├── docker/                 ← Compose, Dockerfiles, Grafana config
└── frontend/               ← React/Vite UI
```

---

## Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLAlchemy (async), Alembic, ARQ, APScheduler |
| Frontend | React 18, Vite, ReactMarkdown, remark-gfm |
| Database | Postgres 16 + pgvector (via pgBouncer) |
| Cache | Redis 7 |
| Graph | Neo4j 5 |
| Observability | Prometheus + Grafana (24 panels, 2 alert rules) |
| Serving | nginx (frontend), uvicorn (API) |
| Infra | Docker Compose; prod variant with TLS + resource limits |

---

## Active Models (verified 2026-05-24)

| Role | Model | Env Var |
|------|-------|---------|
| llama (default) | `meta/llama-3.1-8b-instruct` | `MODEL_LLAMA` |
| coder | `deepseek-ai/deepseek-v4-flash` | `MODEL_CODER` |
| reasoning | `meta/llama-3.3-70b-instruct` | `MODEL_REASONING` |
| embedding | `nvidia/nv-embedqa-e5-v5` (1024d) | `MODEL_EMBEDDING` |

**Dead models (do not use):** `qwen/qwen2.5-coder-32b-instruct` (EOL 410), `mistralai/codestral-22b-instruct-v0.1` (404), `meta/codellama-70b`, `nvidia/llama-3.1-nemotron-70b-instruct`, `ibm/granite-*`, `google/codegemma-*`, `deepseek-ai/deepseek-coder-*`.

**Selection priority:** `per-request model_override > conversation locked_model > keyword router (auto)`

**Fallback chain:** `chosen model → reasoning → coder → llama`

---

## Services & Ports

| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI + uvicorn; runs `alembic upgrade head` on start |
| frontend | 3000 | nginx serving React build |
| pgbouncer | — | transaction mode; 200 max clients, 20 server conns |
| postgres | — | pgvector/pgvector:pg16; internal only |
| redis | — | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s; `prometheusdata` volume persists TSDB |
| grafana | 3001 | admin/admin; 24-panel dashboard; 2 alert rules provisioned |
| metrics-worker | — | `python -m observability.metrics_worker` |
| arq-worker | — | max_jobs=10; handles file processing, insight gen, preference extraction, behavior tracking, notifications |
| scheduler | — | APScheduler; daily memory compaction at 3 AM UTC; **singleton — do not scale** |
| neo4j | 7474/7687 | neo4j:5; auth `neo4j/${NEO4J_PASSWORD:-changeme}` |

---

## Seeded Users

| Username | Password | Role |
|----------|----------|------|
| admin | admin-secret | admin |
| user | user-secret | user |

---

## Backend Structure

```
backend/
├── main.py                  — lifespan, middleware, router includes
├── config.py                — env vars via find_dotenv(); LLM_BACKEND flag (nim|homeserver)
├── core/
│   └── locks.py             — user_write_lock (pg/redis async ctx mgr; MEMORY_LOCK_BACKEND)
├── models/                  — 25 ORM classes across 9+ sub-modules
│   ├── user.py              — User (has_onboarded), UserInsight, AdminAuditLog, UserMemory,
│   │                           UserMemoryVersion, UserBehaviorProfile, UserGoal
│   ├── chat.py              — Conversation, Message, MessageEmbedding, ConversationFile
│   ├── file.py              — File (media_type, ocr_text), FileChunk, FileVersion
│   ├── tools.py             — ToolCallLog
│   ├── prompts_scheduled.py — PromptTemplate, ScheduledPrompt, ScheduledPromptRun
│   ├── auth.py              — Invitation
│   ├── system.py            — SystemConfig, WebhookEvent
│   └── notification.py      — UserNotificationPreferences, PushSubscription (migration 047)
├── alembic/versions/        — 047 migrations; latest: 047_push_subscriptions
├── auth/                    — JWT, bcrypt (direct), API key fallback, invite validation
├── llm/
│   ├── service/             — context build, context budget allocator, SSE stream + tool loop
│   ├── nim.py               — NIM API call; accumulates tool_call deltas
│   ├── tools/               — 25 agent tool schemas + execute_tool()
│   ├── graph_memory.py      — Neo4j extraction (70B) + query_by_keywords
│   ├── router.py            — keyword classify(), classify_intent_hybrid(), model route()
│   ├── circuit_breaker.py   — threshold=5, cooldown=90s, Redis-persisted
│   ├── embeddings.py        — embed(text, input_type) → list[float]; timeout=15s
│   ├── retriever/           — hybrid vector+BM25 fusion (RRF|weighted)
│   ├── summarizer/          — memory compression, compaction, preference extraction
│   └── agency.py            — proactive suggestions + behavior-aware insight generation (ARQ)
├── api/
│   ├── chat/                — POST /chat/stream SSE endpoint; POST /chat non-streaming
│   ├── files/               — upload (OCR-path), ingest-url, search, versions
│   ├── conversations/       — list(?q=), export, PATCH, delete, file attach/detach
│   ├── notifications.py     — prefs CRUD, push subscribe/unsubscribe, VAPID key
│   ├── admin/               — require_role("admin"); users, cost-limit, audit-log, env mgmt
│   ├── graph.py             — /graph/stats, /health, /sample, /prune
│   ├── system.py            — /health, /metrics, /transcribe (VOICE_ENABLED-gated)
│   └── memory.py            — GET /memory; conflict scan/resolve; decay
├── services/
│   ├── processor.py         — extract→chunk→embed; CPU in asyncio.to_thread(); OCR path
│   ├── transcribe.py        — stub ASR dispatcher (faster_whisper slot reserved)
│   ├── notification.py      — email+push dispatch, Redis rate limit
│   ├── arq_worker.py        — _MAX_TRIES=4 (5s/30s/120s backoff); notification ARQ jobs
│   ├── behavior.py          — update_behavior_profile(); pure counter increments, no LLM
│   ├── re_embed.py          — batches of 100; triggered on startup or /admin/re-embed
│   ├── file_service.py      — fuzzy-patch, save-version-before-mutate
│   └── scheduler_worker.py  — APScheduler cron runner
├── services/integrations/
│   ├── google_oauth.py      — GoogleOAuthConnector base; shared by Drive + Calendar
│   ├── gmail.py             — GmailConnector; 3 read-only tools (list/get/search)
│   └── (drive.py, calendar.py, notion.py, github.py)
└── tests/                   — 160+ tests across test.py, retrieval eval, per-feature suites
    ├── test.py
    ├── retrieval/test_hybrid_eval.py  (26 tests, mocked DB)
    └── test_*.py                      (per-feature suites added with each feature)
```

---

## Key Models

- **User** — `cost_limit_usd`/`cost_window_days` cap, `api_key` auth, `is_active` gate, `has_onboarded` bool (migration 046), `email` for digest delivery (migration 041)
- **UserMemory** — `content` text, `salience` float, `confidence` float, `fact_saliences` JSONB, `version` int, `agent_scratchpad` JSONB
- **UserMemoryVersion** — snapshot on every compaction; History tab source
- **UserBehaviorProfile** — one row per user, `profile` JSONB: `query_types / topic_keywords / tools_used / models_used / total_messages`; migration 033
- **UserGoal** — title, description, status (active/completed/paused), `linked_conversation_ids` JSONB; migration 035
- **Conversation** — `title` (auto-titled after 2nd msg), `locked_model`, `system_prompt`, `updated_at`
- **Message** — `content_tsv` GIN for full-text search; `render_meta` JSONB (grounding badge + activity trace, persisted); `token_estimate` bool
- **File** — SHA256 dedup `(user_id, hash)`, `upload_status`, `media_type`, `ocr_text` (migration 045)
- **MemoryConflict** — `fact_a/fact_b/conflict_type/resolution/expires_at`; auto-resolves `keep_a` after 7 days
- **WebhookEvent** — `user_id`, `event_type`, `payload`, `processed_at`; migration 040
- **UserNotificationPreferences** — per-user opt-in flags (digest / scheduled-completion / new-insight), `push_enabled`; migration 047
- **PushSubscription** — VAPID push endpoint + keys per user device; migration 047

---

## ChatRequest Fields

`message` (str, max 2000) · `conversation_id` · `model_override`
`temperature` (0–2) · `max_tokens` (1–4096) · `top_p` (0–1) · `compare` (bool)
`image_b64` (base64 → OCR path on home server) · `image_mime_type` · `file_ids` (list[str])

---

## Memory System

### Context injection order (`build_context_messages`)

| Tier | Block | Drop order |
|------|-------|-----------|
| — | system message (conv sysprompt + file rules) | never |
| — | [GRAPH CONTEXT] Neo4j entity/relation context | low |
| — | [GRAPH FACTS] keyword-triggered neighborhood expansion | low |
| — | [USER STATE] top-20 facts by salience (conflicted suppressed) | low |
| — | [ACTIVE GOALS] active UserGoal rows | low |
| — | [PROJECT STATE] | low |
| — | [RECENT INSIGHTS] top-3 UserInsight (30-day window) | low |
| — | [RELEVANT CONTEXT FROM EARLIER] cosine top-K RAG | medium |
| — | [EARLIER IN THIS CONVERSATION] history summary | medium |
| 8 | [LAST SESSION] last conv title + elapsed time (new conv only) | first to drop |
| — | last 10 importance-weighted messages (history) | last |
| — | [FILE CONTEXT] policy-driven chunks (appended last for recency) | second to drop |
| — | current user message | never |

### Triggers
- Memory update: >3000 tokens OR every 10 assistant messages
- History compression + project summary: >4000 tokens OR every 15 total messages (all_count > 10)
- Auto-title: after 2nd message via `asyncio.create_task`
- Preference extraction: `extract_preferences_job` every 50 assistant messages; writes `[PREFERENCES]` to `UserMemory`; Redis lock `pref_extract:running:{user_id}` EX 300s
- Behavior tracking: `update_behavior_profile_job` every reply; pure counter increments; feeds `generate_user_insight()`
- Compaction: LLM-driven dedup via `compact_memory()`; daily cron 3 AM UTC or ARQ-queued; Redis lock `compact:running:{user_id}` EX 300s

### Salience
- Per-fact `fact_saliences` JSONB; bumped per-access, decayed 0.95/cycle during compaction
- Time-based decay: `0.95^(hours_since_last_compaction/24)` — in-memory only (not persisted)
- Entries below 0.05 pruned; facts below 0.3 salience cleared from sheet
- Retrieval re-ranking: `final_score * (1 + memory_salience * 0.05)`

### Conflict resolver
- `MemoryConflict` stores fact_a, fact_b, conflict_type, resolution, expires_at (+7d)
- Active unresolved facts suppressed from context
- Expired unresolved auto-resolved `keep_a` during context load
- Resolve via `POST /memory/conflicts/{id}/resolve` strategy: `keep_a|keep_b|merge|discard_both`

### Context budget allocator
- Drops lowest-tier sources when estimated tokens exceed `context_window - max_output_tokens - 10%`
- Re-applied after each tool iteration
- [LAST SESSION] drops first (tier 8); [FILE CONTEXT] drops second

---

## AI Agent Tool Loop

- **Trigger:** any message when `file_ids` non-empty → forces reasoning model (70B)
- **Tools (25):** `list_files` · `read_file` · `write_file` · `create_file` · `append_to_file` · `patch_file` (fuzzy) · `search_in_file` · `search_across_files` · `ask_user` · `query_graph` · `write_memory` · `web_search` · `fetch_url` · `drive_list_files` · `drive_search` · `drive_read_file` · `calendar_list_events` · `calendar_get_event` · `calendar_search_events` · `calendar_create_event` · `calendar_update_event` · `calendar_delete_event` · `gmail_list_messages` · `gmail_get_message` · `gmail_search_messages` (connector tools keyword-gated, injected only on noun+action match)
- **Guards:** same tool + identical args repeated → abort after `_MAX_IDENTICAL_CALLS=3` (listing + connector tools override to 1); distinct-arg bulk ops flow freely; `MAX_TOOL_ITERATIONS=60` hard cap; tool result capped 12000 chars in context
- **`ask_user`:** yields `{type:"ask_user"}` SSE + done → pauses loop; amber card in UI
- **`write_memory`:** offered only when reasoning model selected AND `_needs_memory_tool()` returns true; yields `{type:"confirm_write_memory", fact}` SSE; green card in UI; user confirms → `POST /api/memory/write`
- **Calendar writes:** `create/update/delete` return a `__CONFIRM_CALENDAR_WRITE__:` sentinel → SSE `confirm_calendar_write` → UI confirm card → Accept calls `POST /api/integrations/calendar/execute`

---

## Hybrid Retrieval

- Vector (pgvector cosine) + BM25 parallel → RRF (k=60) or weighted fusion
- Adaptive policy: `classify_query()` returns `factual|relational|temporal|broad`
  - factual = weighted fusion α=0.7
  - relational = RRF
  - temporal = RRF low-k
  - broad = weighted α=0.3
- Intent-aware tuning: `classify_intent_hybrid()` (keyword fast-path + 8B fallback); exploration `top_k+=4`, question `top_k-=1`
- Fallback to pure vector if BM25 unavailable
- Debug mode: `retrieve(debug=True)` returns `(chunks, debug_info)`; `/search?debug=true`

---

## File Knowledge Base

- Upload: SHA256 streaming → dedup `(user_id, hash)` → ARQ job or inline fallback
- Formats: PDF · DOCX (+ tables after paragraphs) · XLSX/XLS · text/code/markdown · images (OCR → text)
- Image OCR: PaddleOCR via `IMAGE_OCR_ENABLED` (default false); both upload and chat paste paths; scanned-PDF fallback (pypdfium2 render → per-page OCR, `_PDF_OCR_MAX_PAGES=20`)
- Chunks: 1600 chars, 200 overlap, sentence-aligned tail
- **File RAG requires explicit attachment** (Library → + button); upload alone is not sufficient
- Status SSE: polls `db.refresh` + Redis `proc_progress:{file_id}` every 0.8s

---

## Reliability Settings

| Setting | Value |
|---------|-------|
| NIM retries | `MAX_RETRIES=3` (4 total); exponential+jitter backoff; up to ~10s |
| Circuit breaker | 5 failures → open; 90s cooldown; Redis-persisted; pre-tripped on startup |
| Request timeout | `REQUEST_TIMEOUT` env (default 30s) |
| Max concurrent | `MAX_CONCURRENT_REQUESTS` env (default 10, cap 50) |
| Rate limit (chat) | 15 req / 60s per user |
| Rate limit (per-model) | llama=15, coder=10, reasoning=5 req/60s (explicit selection only) |
| Cache bypass | file_chunks / image_b64 / model_params present |
| Memory write lock | `user_write_lock` (pg_advisory_xact_lock or Redis; `MEMORY_LOCK_BACKEND` env, default pg) |
| Tool loop guard | max 60 iterations; same tool + identical args repeated → abort after 3 (listing/connector tools after 1) |

---

## SSE Events (POST /chat/stream)

| Event type | Fields |
|------------|--------|
| `token` | `content` |
| `tool_call` | `name`, `arguments` |
| `tool_result` | `name`, `result` |
| `ask_user` | — |
| `confirm_write_memory` | `fact` |
| `confirm_calendar_write` | `op`, `args` (calendar write pending user confirm) |
| `proactive` | `content` |
| `done` | `model`, `cache_hit`, `fallback_used`, `usage`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `provenance[]`, `query_type`, `src_count`, `intent`, `grounding{level,score,sources}`, `activity[]`, `last_session`, `conversation_id` |
| `error` | `message` |

---

## Frontend Structure

```
frontend/src/
├── App.jsx                  — login form; JWT stored as nim_token in localStorage
├── components/
│   ├── Chat/                — orchestrator (index.jsx); imports all hooks + sub-components
│   └── chat/
│       ├── Sidebar.jsx      — conversation list, search
│       ├── MessageList/     — message rendering; grounding badge + activity trace; markdown
│       ├── ModelToolbar.jsx — model pills, compare mode, params modal, mic button (voice)
│       ├── MemoryPanel.jsx  — tabs: View / Edit / History / Graph / Conflicts
│       ├── FilesPanel.jsx   — Library + Attached tabs; SSE processing status; image thumbnails
│       ├── FileViewer.jsx   — View / Edit / Versions / Preview (OCR text) tabs
│       ├── ToolLogPanel.jsx — per-call tool log, filter by conv
│       ├── UsagePanel.jsx   — aggregate token/cost stats; Export All Data button
│       ├── InsightsPanel.jsx — unread badge, mark-read, delete
│       ├── InvitePanel.jsx  — admin invite token management
│       ├── SearchPanel.jsx  — unified search (files/convs/memory/graph); img badge
│       ├── AutomationsPanel.jsx — scheduled prompts CRUD + run history
│       ├── GoalsPanel.jsx   — user goals CRUD + conversation linking
│       ├── IntegrationsPanel/ — OAuth connectors (Drive, Calendar, Gmail, Notion, GitHub)
│       ├── SettingsModal.jsx — notification preferences (email + push toggles)
│       └── OnboardingModal/ — 3-step skippable wizard (Welcome → Email → Integrations)
└── hooks/                   — 17 hooks
    ├── useStreamChat.js      useConversations.js  useMemory.js
    ├── useFiles.js           useGoals.js          useScheduledPrompts.js
    ├── useSearch.js          useInsights.js       useIntegrations.js
    ├── useToolLogs.js        useUsage.js          useAdmin.js
    ├── useModelParams.js     useSettings.js
    ├── useVoice.js           — MediaRecorder + POST /api/transcribe
    ├── useOnboarding.js      — onboarding wizard state + completion
    └── useNotificationPrefs.js — prefs CRUD + push subscribe/unsubscribe
```

---

## Admin / Cost

- Cost cap: rolling window (`cost_window_days`, default 30, null=all-time) → 402 on exceed
- Audit actions: `user.active.enabled/disabled` · `user.cost_limit.set/removed` · `env.updated` · `env.reloaded`
- Model pricing: llama $0.10/$0.10 · coder $0.20/$0.60 · reasoning $0.77/$0.77 per 1M tokens
- Self-disable blocked; `is_active` checked on every `get_current_user`

---

## Non-obvious Invariants

- pgBouncer transaction mode → `prepared_statement_cache_size=0` required; `pool_pre_ping=False`
- `AUTH_TYPE=plain` required in pgBouncer — pg16 uses scram-sha-256, md5/trust do not work
- `DATABASE_URL` for api + scheduler → `pgbouncer:5432` (never `postgres:5432`)
- Cache key v2: `msg + model + history[-4] + sysprompt`; bypassed on image_b64 / model_params / ConversationFile
- ARQ: api enqueues → arq-worker consumes; inline fallback when pool unavailable
- SHA256 dedup: returns existing file + `duplicate: true` — no re-upload
- Sync file I/O + CPU parsing wrapped in `asyncio.to_thread()`
- Auth uses `bcrypt` directly (no passlib) — `$2b$` hashes compatible
- Neo4j: MERGE SET preserves specific type over OTHER; 500-entity cap per user (evicts oldest); graph cache in Redis 60s TTL; busted on every entity write
- `/admin/env` PUT writes `.env` + updates running config live; POST `/admin/env/reload` does `importlib.reload(config)`
- `nginx.frontend.conf`: `resolver 127.0.0.11 valid=10s` + `set $upstream api` forces Docker DNS re-resolution after rebuilds; `rewrite ^/api/(.*) /$1 break` strips prefix
- Prometheus: multiprocess mode via `PROMETHEUS_MULTIPROC_DIR=/tmp/prom_multiproc` + `tmpfs`; in-process counters reset on container restart but TSDB volume persists rates
- `MEMORY_LOCK_BACKEND=pg` (default) uses `pg_advisory_xact_lock(user_id)`; `redis` uses distributed lock via `core/locks.py:user_write_lock`; switch is inert by default
- Scheduler is a **singleton** — never run `--scale scheduler=N`; API + ARQ workers are stateless and freely scalable

---

## Known Issues

- No chat integration tests — `/chat` requires live NIM API; retrieval covered by 26 mock-DB tests
- File RAG requires explicit attachment (Library → + button); upload alone insufficient
- `_needs_file_tools` is keyword-based — may miss implicit file requests
- Token counts on pre-migration 011 messages are NULL (migration 032 backfills with character heuristic; `token_estimate=true` flags estimated rows)
- Prometheus in-process counters reset on container restart — mitigated by volume + multiprocess mode
- Reasoning trace is pipeline-level only — `activity[]` shows retrieval/intent/routing/tools, not model chain-of-thought (llama-3.3-70b emits no native thinking tokens)

---

## Roadmap Status (as of 2026-06-21)

**P0 + P1 + P2 + P3 complete. ~99% overall.**

### P0–P2 (all ✅)
Autonomous memory writing · Preference extraction · Behavioral pattern tracker · Cross-session continuity · Memory conflict resolution UI · Fact-level salience panel · Unified search · Knowledge graph explorer UI · Memory timeline view · Full data export · Scheduled backup · User-defined scheduled agents · Goal/task tracker · Pattern detection + triggers · Web search tool · Event-driven triggers · Daily/weekly digest

### P3 (all ✅)
Live webpage ingestion · External integrations (Drive + Calendar + Notion + GitHub + Gmail) · Image CPU-OCR (#19, `IMAGE_OCR_ENABLED`) · Scanned-PDF OCR fallback · Voice input STT (#20, `VOICE_ENABLED`, stub transcriber) · Horizontal scaling (#21, `MEMORY_LOCK_BACKEND`, nginx dynamic DNS) · Onboarding wizard (`has_onboarded`, 3-step skippable) · Out-of-UI notifications (email + web push, `UserNotificationPreferences`)

### Remaining / Blocked
- **#22 Multi-Modal Memory** — trigger-gated (BUGS Q-D2); build only on trigger
- **Outlook/CalDAV / Gmail write** — deferred; promote + spec if wanted
- **Real ASR (Whisper)** → `QUEUE.md` Q2 (box-blocked; STT stub already ships)
- **Home-server port** → `QUEUE.md` Q1 (box-blocked: 2×P40)

### Vision Alignment

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| 1. Persistent Memory | 97% | P0 complete |
| 2. Unified Interface | 100% | Cross-conv insight propagation shipped |
| 3. Reasoning Loop | ~97% | Pipeline trace + grounding badge; model CoT ceiling (no native thinking tokens) |
| 4. Autonomous Agency | 90% | P2 complete; goal tracker + digest + triggers |
| 5. Real-Time Perception | 95% | Web search + live fetch + Drive + Calendar + Gmail + OCR + notifications; Outlook/CalDAV open |
| **Overall** | **~99%** | |

---

## HANDOFF Protocol

- **Root** — plans, writes HANDOFF.md, delegates. Does not implement code.
- **backend/** — implements backend tasks only. Does not plan.
- **frontend/** — implements frontend tasks only. Does not plan.
- **docker/** — implements infra tasks only. Does not plan.
- **Exactly one `HANDOFF.md`** in the entire project at all times. Location = current owner. Move with `mv`, never create a second copy.
- **`QUEUE.md`** (root-owned) holds deferred/planned features not yet active; root promotes an entry into `HANDOFF.md` when the slot frees and prerequisites are met.
- Root-owned files workers must not edit: `.env` · `.env.example` · `.gitignore` · `.dockerignore` · root `CLAUDE.md` · `README.md` · `ROADMAP.md` · `QUEUE.md`
