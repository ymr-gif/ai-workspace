# NIM AI Gateway — Project Summary

Generated: 2026-06-10

> ⚠️ **Snapshot — parts are stale.** Structure counts, the tool list, and the "Roadmap Status"
> section below reflect 2026-06-10 and have drifted (current: ~044 migrations · 24 ORM · 16 tools ·
> `MAX_TOOL_ITERATIONS=60`). Authoritative live docs: `backend/CLAUDE.md`, `ROADMAP.md`, `BUGS.md`.

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

> Note: the "Roadmap Status" section near the bottom of this file is stale (dated 2026-05-31) — see `ROADMAP.md` for current status (P0+P1+P2 done, most of P3 done).

---

## Repo Layout

```
ai-api/
├── .env                    ← secrets (gitignored); loaded by find_dotenv()
├── .env.example            ← all supported vars documented
├── CLAUDE.md               ← root project reference
├── ROADMAP.md              ← vision, backlog, implementation order
├── COMMANDS.md             ← common dev commands
├── BUGS.md                 ← bug tracker
├── HANDOFF_PROTOCOL.md     ← multi-agent delegation workflow
├── HANDOFF.md              ← current owner file (exactly one at all times)
├── QUEUE.md                ← deferred/planned features backlog (root-owned)
├── HANDOFF_ARCHIVE.md      ← completed handoff records
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
| arq-worker | — | max_jobs=10; handles file processing, insight gen, preference extraction, behavior tracking |
| scheduler | — | APScheduler; daily memory compaction at 3 AM UTC |
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
├── config.py                — env vars via find_dotenv()
├── models/                  — 23 ORM classes across 8 sub-modules
│   ├── user.py              — User, UserInsight, AdminAuditLog, UserMemory, UserMemoryVersion
│   ├── chat.py              — Conversation, Message, MessageEmbedding, ConversationFile
│   ├── file.py              — File, FileChunk, FileVersion
│   ├── tools.py             — ToolCallLog
│   ├── prompts_scheduled.py — PromptTemplate, ScheduledPrompt, ScheduledPromptRun
│   ├── auth.py              — Invitation
│   └── system.py            — SystemConfig
├── alembic/versions/        — 037 migrations; latest: 037_drop_workspaces.py (removed the workspace layer)
├── auth/                    — JWT, bcrypt (direct), API key fallback, invite validation
├── llm/
│   ├── service/             — context build, context budget allocator, SSE stream + tool loop
│   ├── nim.py               — NIM API call; accumulates tool_call deltas
│   ├── tools/               — 11 tool schemas + execute_tool()
│   ├── graph_memory.py      — Neo4j extraction (70B) + query_by_keywords
│   ├── router.py            — keyword classify(), model route(), get_context_limit()
│   ├── circuit_breaker.py   — threshold=5, cooldown=90s, Redis-persisted
│   ├── embeddings.py        — embed(text, input_type) → list[float]; timeout=15s
│   ├── retriever/           — hybrid vector+BM25 fusion (RRF|weighted)
│   ├── summarizer/          — memory compression, compaction, preference extraction
│   └── agency.py            — proactive suggestions + behavior-aware insight generation (ARQ)
├── api/
│   ├── chat/                — POST /chat/stream SSE endpoint; POST /chat non-streaming
│   ├── files/               — upload, ingest-url, search, versions
│   ├── conversations/       — list(?q=), export, PATCH, delete, file attach/detach
│   ├── admin/               — require_role("admin"); users, cost-limit, audit-log, env mgmt
│   ├── graph.py             — /graph/stats, /health, /sample, /prune
│   ├── system.py            — /health, /metrics; probe_models_on_startup()
│   └── memory.py            — GET /memory; conflict scan/resolve; decay
├── services/
│   ├── processor.py         — extract→chunk→embed; CPU in asyncio.to_thread()
│   ├── arq_worker.py        — _MAX_TRIES=4 (5s/30s/120s backoff)
│   ├── behavior.py          — update_behavior_profile(); pure counter increments, no LLM
│   ├── re_embed.py          — batches of 100; triggered on startup or /admin/re-embed
│   ├── file_service.py      — fuzzy-patch, save-version-before-mutate
│   └── scheduler_worker.py  — APScheduler cron runner
└── tests/
    ├── test.py              — 21 unit tests (standalone, no docker)
    └── retrieval/test_hybrid_eval.py — 26 tests (mock DB, no NIM)
```

---

## Key Models

- **User** — `cost_limit_usd`/`cost_window_days` cap, `api_key` auth, `is_active` gate
- **UserMemory** — `content` text, `salience` float (1.0 default), `confidence` float, `fact_saliences` JSONB (per-line scores), `version` int, `agent_scratchpad` JSONB (agent notes, cross-session context)
- **UserMemoryVersion** — snapshot on every compaction; History tab source
- **UserBehaviorProfile** — one row per user, `profile` JSONB: `query_types / topic_keywords / tools_used / models_used / total_messages`; migration 033
- **Conversation** — `title` (auto-titled after 2nd msg), `locked_model`, `system_prompt`, `updated_at` (timezone-aware)
- **Message** — `content_tsv` GIN for full-text search; `token_estimate` bool (null = real NIM data, true = character heuristic backfill from migration 032)
- **File** — SHA256 dedup `(user_id, hash)`, `upload_status`: `uploaded|processing|ready|partial|failed|error`
- **MemoryConflict** — `fact_a/fact_b/conflict_type/resolution/expires_at`; auto-resolves `keep_a` after 7 days

---

## ChatRequest Fields

`message` (str, max 2000) · `conversation_id` · `model_override`
`temperature` (0–2) · `max_tokens` (1–4096) · `top_p` (0–1) · `compare` (bool)
`image_b64` (base64 → forces vision) · `image_mime_type` · `file_ids` (list[str])

---

## Memory System

### Context injection order (`build_context_messages`)

| Tier | Block | Drop order |
|------|-------|-----------|
| — | system message (conv sysprompt + file rules) | never |
| — | [GRAPH CONTEXT] Neo4j entity/relation context | low |
| — | [GRAPH FACTS] keyword-triggered neighborhood expansion | low |
| — | [USER STATE] top-20 facts by salience (conflicted suppressed) | low |
| — | [PROJECT STATE] | low |
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
- **Tools (11):** `list_files` · `read_file` · `write_file` · `create_file` · `append_to_file` · `patch_file` (fuzzy) · `search_in_file` · `search_across_files` · `ask_user` · `query_graph` · `write_memory`
- **Guards:** same tool >3× → abort; `MAX_TOOL_ITERATIONS=10`; tool result capped 12000 chars in context
- **`ask_user`:** yields `{type:"ask_user"}` SSE + done → pauses loop; amber card in UI
- **`write_memory`:** offered only when reasoning model selected AND `_needs_memory_tool()` returns true; yields `{type:"confirm_write_memory", fact}` SSE; green card in UI; user confirms → `POST /api/memory/write`

---

## Hybrid Retrieval

- Vector (pgvector cosine) + BM25 parallel → RRF (k=60) or weighted fusion
- Adaptive policy: `classify_query()` returns `factual|relational|temporal|broad`
  - factual = weighted fusion α=0.7
  - relational = RRF
  - temporal = RRF low-k
  - broad = weighted α=0.3
- Fallback to pure vector if BM25 unavailable
- Debug mode: `retrieve(debug=True)` returns `(chunks, debug_info)`; `/search?debug=true`

---

## File Knowledge Base

- Upload: SHA256 streaming → dedup `(user_id, hash)` → ARQ job or inline fallback
- Formats: PDF · DOCX (+ tables after paragraphs) · XLSX/XLS · text/code/markdown
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
| Memory write lock | `pg_advisory_xact_lock(user_id)` prevents version races |
| Tool loop guard | max 10 iterations; >3 same tool → abort |

---

## SSE Events (POST /chat/stream)

| Event type | Fields |
|------------|--------|
| `token` | `content` |
| `tool_call` | `name`, `arguments` |
| `tool_result` | `name`, `result` |
| `ask_user` | — |
| `confirm_write_memory` | `fact` |
| `proactive` | `content` |
| `done` | `model`, `cache_hit`, `fallback_used`, `usage`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `provenance[]`, `query_type`, `src_count`, `last_session`, `conversation_id` |
| `error` | `message` |

---

## Frontend Structure

```
frontend/src/
├── App.jsx                  — login form; JWT stored as nim_token in localStorage
├── components/
│   ├── Chat.jsx             — orchestrator; 400+ lines; imports all hooks + sub-components
│   └── chat/
│       ├── Sidebar.jsx      — conversation list, search
│       ├── MessageList.jsx  — message rendering; last session banner; markdown; tool calls
│       ├── ModelToolbar.jsx — model pills, compare mode, params modal, settings modal
│       ├── MemoryPanel.jsx  — tabs: View / Edit / History / Graph / Conflicts
│       ├── FilesPanel.jsx   — Library + Attached tabs; SSE processing status
│       ├── FileViewer.jsx   — View / Edit / Versions tabs
│       ├── ToolLogPanel.jsx — per-call tool log, filter by conv
│       ├── UsagePanel.jsx   — aggregate token/cost stats
│       ├── InsightsPanel.jsx — unread badge, mark-read, delete
│       └── InvitePanel.jsx  — admin invite token management
└── hooks/                   — 13 hooks (useConversations, useMemory, useFiles,
                               useModelParams, useSettings, useToolLogs,
                               useUsage, useAdmin, useInsights, useSearch,
                               useScheduledPrompts, useGoals, useStreamChat)
```

### Key UI Behaviors

- **Streaming:** raw `<p>` + blinking cursor during stream → `<ReactMarkdown>` on done
- **Per-bubble metadata:** `{totalTokens} tok · $x.xxxxx · [query_type] · N src`; src badge green ≥3, amber 1–2, hidden 0
- **Last session banner:** `✦ Last session: "…" — X ago` above first AI bubble on new conversations; auto-dismisses 8s; cleared on next send
- **Proactive suggestion:** indigo card on `{type:"proactive"}` SSE; clears on next send
- **ask_user card:** amber "NEEDS CLARIFICATION"; reply resumes with full context
- **confirm_write_memory card:** green "MEMORY SUGGESTION"; Accept → `POST /api/memory/write`; Dismiss → null
- **All fetch calls use `/api/` prefix** — bare paths bypass proxy and 404 silently

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
- `nginx.frontend.conf`: `resolver 127.0.0.11 valid=10s` + `set $upstream api` forces Docker DNS re-resolution after rebuilds; `rewrite ^/api/(.*) /$1 break` strips prefix (variable proxy_pass does NOT auto-strip)
- Prometheus: multiprocess mode via `PROMETHEUS_MULTIPROC_DIR=/tmp/prom_multiproc` + `tmpfs`; in-process counters reset on container restart but TSDB volume persists rates

---

## Known Issues

- No chat integration tests — `/chat` requires live NIM API; retrieval covered by 26 mock-DB tests
- File RAG requires explicit attachment (Library → + button); upload alone insufficient
- `_needs_file_tools` is keyword-based — may miss implicit file requests
- Token counts on pre-migration 011 messages are NULL (migration 032 backfills with character heuristic; `token_estimate=true` flags estimated rows)
- Prometheus in-process counters reset on container restart — mitigated by volume + multiprocess mode

---

## Roadmap Status (as of 2026-05-31)

**P0 + P1 complete. P2 in progress (#12, #14 done).** Overall vision alignment: ~82%.

### P0 — Core Cognition (all ✅)
1. ✅ Autonomous Memory Writing — `write_memory` tool; user-confirm green card
2. ✅ User Preference Extraction — `extract_preferences_job`; `[PREFERENCES]` in UserMemory
3. ✅ Behavioral Pattern Tracker — `UserBehaviorProfile` JSONB; ARQ every reply; feeds insight gen
4. ✅ Cross-Session Continuity Summary — `[LAST SESSION]` tier-8 context block; `done.last_session` SSE field; banner UI

### P1 — Platform Completeness (all ✅)
5. ✅ Memory Conflict Resolution UI — Conflicts tab in MemoryPanel; `useMemory.js` state; per-card type badge + resolve buttons
6. ✅ Fact-Level Salience Panel — score bar (4px, color-coded) + last-access timestamp per fact
7. ✅ Unified Search — `GET /api/search?q=&scope=`; fan-out via `asyncio.gather`; `SearchPanel.jsx` + `useSearch.js`
8. ✅ Knowledge Graph Explorer UI — SVG circle-layout graph; click-to-highlight; entity_type + limit filters
9. ✅ Memory Timeline View — `GET /memory/history`; expandable diff view in History tab
10. ✅ Full Data Export — `GET /api/export/full`; ZIP stream; export button in `UsagePanel.jsx`
11. ✅ Scheduled Backup — `run_backup()` in `scheduler_worker.py`; `BACKUP_SCHEDULE` env var (default `0 2 * * *`)

### P2 — Autonomous Agency (in progress)
12. ✅ User-Defined Scheduled Agents — `AutomationsPanel.jsx`; `useScheduledPrompts.js`; full CRUD + run history; cron alias support; migration 034
13. ✅ Goal / Task Tracker — `UserGoal` model; `[ACTIVE GOALS]` context block (tier 3); `GoalsPanel.jsx` + `useGoals.js`; migration 035
14. ✅ Pattern Detection + Proactive Triggers — `detect_recurring_patterns()`; 7-day dedup guard; ARQ enqueue with hint; `agency.py` merged + hint kwarg
~~15. Global Autonomous Agent Canvas~~ — removed 2026-06-09
16. Web Search Tool — `WEB_SEARCH_ENABLED` + `WEB_SEARCH_BACKEND` env vars
17. Daily/Weekly Digest

### P3 — Future
Live webpage ingestion · External integrations (Drive, Notion, GitHub) · Image storage + indexing · Voice input · Horizontal scaling (Redis distributed locks replacing pg advisory) · Multi-modal memory

### Vision Alignment

| Dimension | Coverage |
|-----------|----------|
| 1. Persistent Memory | 97% |
| 2. Unified Interface | 90% |
| 3. Reasoning Loop | 65% |
| 4. Autonomous Agency | 60% |
| 5. Real-Time Perception | 10% |
| **Overall** | **~82%** |

---

## HANDOFF Protocol

- **Root** — plans, writes HANDOFF.md, delegates. Does not implement code.
- **backend/** — implements backend tasks only. Does not plan.
- **frontend/** — implements frontend tasks only. Does not plan.
- **docker/** — implements infra tasks only. Does not plan.
- **Exactly one `HANDOFF.md`** in the entire project at all times. Location = current owner. Move with `mv`, never create a second copy.
- **`QUEUE.md`** (root-owned) holds deferred/planned features not yet active; root promotes an entry into `HANDOFF.md` when the slot frees and prerequisites are met. Currently queued: Home-Server Port → #19 Image/CPU-OCR → #22 → P3 tail.
- Root-owned files workers must not edit: `.env` · `.env.example` · `.gitignore` · `.dockerignore` · root `CLAUDE.md` · `README.md` · `ROADMAP.md`

