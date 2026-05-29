# NIM AI Gateway — Project Summary

Generated: 2026-05-30

---

## What This Is

FastAPI backend routing chat messages to NVIDIA NIM models via keyword classification.
React/Vite frontend. Docker Compose stack: Postgres + pgvector, Redis, Neo4j, Prometheus, Grafana.

**Vision:** A multi-user AI system where each person has a private, continuously evolving digital mind
that unifies memory, reasoning, and future autonomous intelligence into one personalized cognitive workspace.

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
├── models/                  — 20 ORM classes across 8 sub-modules
│   ├── user.py              — User, UserInsight, AdminAuditLog, UserMemory, UserMemoryVersion
│   ├── chat.py              — Conversation, Message, MessageEmbedding, ConversationFile
│   ├── file.py              — File, FileChunk, FileVersion
│   ├── workspace.py         — Workspace, WorkspaceMemory
│   ├── tools.py             — ToolCallLog
│   ├── prompts_scheduled.py — PromptTemplate, ScheduledPrompt, ScheduledPromptRun
│   ├── auth.py              — Invitation
│   └── system.py            — SystemConfig
├── alembic/versions/        — 033 migrations; latest: 033_user_behavior_profile.py
├── auth/                    — JWT, bcrypt (direct), API key fallback, invite validation
├── llm/
│   ├── service/             — context build, context budget allocator, SSE stream + tool loop
│   ├── nim.py               — NIM API call; accumulates tool_call deltas
│   ├── tools/               — 10 tool schemas + execute_tool()
│   ├── graph_memory.py      — Neo4j extraction (70B) + query_by_keywords
│   ├── router.py            — keyword classify(), model route(), get_context_limit()
│   ├── circuit_breaker.py   — threshold=5, cooldown=90s, Redis-persisted
│   ├── embeddings.py        — embed(text, input_type) → list[float]; timeout=15s
│   ├── retriever/           — hybrid vector+BM25 fusion (RRF|weighted)
│   ├── summarizer/          — memory compression, compaction, preference extraction, workspace memory
│   └── agency.py            — proactive suggestions + behavior-aware insight generation (ARQ)
├── api/
│   ├── chat/                — POST /chat/stream SSE endpoint; POST /chat non-streaming
│   ├── workspaces.py        — /workspaces CRUD + memory routes
│   ├── files/               — upload, ingest-url, search, versions, workspace assign
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
- **UserMemory** — `content` text, `salience` float (1.0 default), `confidence` float, `fact_saliences` JSONB (per-line scores), `version` int
- **UserMemoryVersion** — snapshot on every compaction; History tab source
- **UserBehaviorProfile** — one row per user, `profile` JSONB: `query_types / topic_keywords / tools_used / models_used / total_messages`; migration 033
- **Conversation** — `title`, `locked_model`, `workspace_id`, `updated_at` (timezone-aware)
- **Message** — `content_tsv` GIN for full-text search; `token_estimate` bool (null = real NIM data, true = character heuristic backfill from migration 032)
- **File** — SHA256 dedup `(user_id, hash)`, `upload_status`: `uploaded|processing|ready|partial|failed|error`
- **MemoryConflict** — `fact_a/fact_b/conflict_type/resolution/expires_at`; auto-resolves `keep_a` after 7 days

---

## ChatRequest Fields

`message` (str, max 2000) · `conversation_id` · `workspace_id` (UUID) · `model_override`
`temperature` (0–2) · `max_tokens` (1–4096) · `top_p` (0–1) · `compare` (bool)
`image_b64` (base64 → forces vision) · `image_mime_type`

---

## Memory System

### Context injection order (`build_context_messages`)

| Tier | Block | Drop order |
|------|-------|-----------|
| — | system message (workspace + conv sysprompt + file rules) | never |
| — | [GRAPH CONTEXT] Neo4j entity/relation context | low |
| — | [GRAPH FACTS] keyword-triggered neighborhood expansion | low |
| — | [USER STATE] top-20 facts by salience (conflicted suppressed) | low |
| — | [WORKSPACE STATE] · [PROJECT STATE] | low |
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
- **Tools (10):** `list_files` · `read_file` (100k cap, 12000 char context limit) · `write_file` · `create_file` · `append_to_file` · `patch_file` (fuzzy) · `search_in_file` · `search_across_files` · `ask_user` · `query_graph` · `write_memory`
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
│       ├── Sidebar.jsx      — conversation list, workspace filter pills, search
│       ├── MessageList.jsx  — message rendering; last session banner; markdown; tool calls
│       ├── ModelToolbar.jsx — model pills, compare mode, params modal, settings modal
│       ├── MemoryPanel.jsx  — tabs: View / Workspace / Edit / History / Graph
│       ├── FilesPanel.jsx   — Library + Attached tabs; SSE processing status
│       ├── FileViewer.jsx   — View / Edit / Versions tabs
│       ├── ToolLogPanel.jsx — per-call tool log, filter by conv
│       ├── UsagePanel.jsx   — aggregate token/cost stats
│       ├── InsightsPanel.jsx — unread badge, mark-read, delete
│       ├── InvitePanel.jsx  — admin invite token management
│       └── WorkspaceModal.jsx — create/edit workspace
└── hooks/                   — 10 hooks (useConversations, useMemory, useWorkspace,
                               useFiles, useModelParams, useSettings, useToolLogs,
                               useUsage, useAdmin, useInsights)
```

### Key UI Behaviors

- **Streaming:** raw `<p>` + blinking cursor during stream → `<ReactMarkdown>` on done
- **Per-bubble metadata:** `{totalTokens} tok · $x.xxxxx · [query_type] · N src`; src badge green ≥3, amber 1–2, hidden 0
- **Last session banner:** `✦ Last session: "…" — X ago` above first AI bubble on new conversations; auto-dismisses 8s; cleared on next send
- **Proactive suggestion:** indigo card on `{type:"proactive"}` SSE; clears on next send
- **ask_user card:** amber "NEEDS CLARIFICATION"; reply resumes with full context
- **confirm_write_memory card:** green "MEMORY SUGGESTION"; Accept → `POST /api/memory/write`; Dismiss → null
- **Workspace filter:** `localStorage` key `nim_sidebar_ws_id`; validated on mount, cleared if stale
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

## Roadmap Status (as of 2026-05-30)

**All P0 complete.** Overall vision alignment: ~58%.

### P0 — Core Cognition (all ✅)
1. ✅ Autonomous Memory Writing — `write_memory` tool; user-confirm green card
2. ✅ User Preference Extraction — `extract_preferences_job`; `[PREFERENCES]` in UserMemory
3. ✅ Behavioral Pattern Tracker — `UserBehaviorProfile` JSONB; ARQ every reply; feeds insight gen
4. ✅ Cross-Session Continuity Summary — `[LAST SESSION]` tier-8 context block; `done.last_session` SSE field; banner UI

### P1 — Platform Completeness (next sprint)
5. Memory Conflict Resolution UI (backend ✅, frontend pending)
6. Fact-Level Salience Panel — badge done; score bar + timestamp remaining
7. Unified Search — `/api/search?scope=all|files|conversations|memory|graph`
8. Knowledge Graph Explorer UI — `react-force-graph` or `vis-network`
9. ✅ Memory Timeline View (backend ✅, frontend ✅)
10. Full Data Export / Portability — ZIP of all conversations, files, memory, graph
11. Scheduled Backup — APScheduler calling `backup.sh`

### P2 — Autonomous Agency
12. User-Defined Scheduled Agents (ScheduledPrompt CRUD already partial)
13. Goal / Task Tracker — `UserGoal` model + `[ACTIVE GOALS]` context block
14. Pattern Detection + Proactive Triggers
15. Web Search Tool — `WEB_SEARCH_ENABLED` + `WEB_SEARCH_BACKEND` env vars
16. Daily/Weekly Digest

### P3 — Future
Live webpage ingestion · External integrations (Drive, Notion, GitHub) · Image storage + indexing · Voice input · Horizontal scaling (Redis distributed locks replacing pg advisory) · Multi-modal memory

### Vision Alignment

| Dimension | Coverage |
|-----------|----------|
| 1. Persistent Memory | 97% |
| 2. Unified Interface | 60% |
| 3. Reasoning Loop | 65% |
| 4. Autonomous Agency | 35% |
| 5. Real-Time Perception | 10% |
| **Overall** | **~58%** |

---

## HANDOFF Protocol

- **Root** — plans, writes HANDOFF.md, delegates. Does not implement code.
- **backend/** — implements backend tasks only. Does not plan.
- **frontend/** — implements frontend tasks only. Does not plan.
- **docker/** — implements infra tasks only. Does not plan.
- **Exactly one `HANDOFF.md`** in the entire project at all times. Location = current owner. Move with `mv`, never create a second copy.
- Root-owned files workers must not edit: `.env` · `.env.example` · `.gitignore` · `.dockerignore` · root `CLAUDE.md` · `README.md` · `ROADMAP.md`

---

---

# Verification Session — Cross-Session Continuity Summary (ROADMAP #4)

**Date:** 2026-05-30  
**Triggered by:** `/verify`  
**Feature verified:** Cross-Session Continuity Summary — the last completed ROADMAP item before this session.

---

## What the Feature Does

When a user starts a **new** conversation (not replying to an existing one), the backend:
1. Looks up the most recently updated conversation that is NOT the current one
2. Formats a string: `Last session: "<title>" — X minutes/hours/days ago`
3. Injects it as a `[LAST SESSION]` block (tier 8 in context priority — first to drop under budget pressure)
4. Emits it in the SSE `done` event as `last_session`

The frontend:
1. Reads `event.last_session` from the SSE `done` event
2. Stores it in `lastSession` state (in `useConversations.js`)
3. Renders `✦ Last session: "…" — X ago` as a muted dim line above the first AI bubble
4. Auto-dismisses after 8 seconds via `useEffect` + `setTimeout`
5. Clears immediately on next message send via `conv.setLastSession('')`

**Files touched by the feature:**
- `backend/api/chat/helpers.py` — query for last conversation, build `last_session` string
- `backend/api/chat/stream.py` — pass `last_session` to `generate_stream`; add to `done` event
- `backend/llm/service/context.py` — accept `last_session` param; inject as `[LAST SESSION]` block; tier-8 budget priority
- `backend/llm/service/stream.py` — thread `last_session` through `generate_stream` signature
- `frontend/src/hooks/useConversations.js` — `lastSession` + `setLastSession` state
- `frontend/src/components/Chat.jsx` — read `event.last_session` from SSE; 8s auto-dismiss `useEffect`; pass `lastSession` to `MessageList`; clear on send
- `frontend/src/components/chat/MessageList.jsx` — render banner above first AI bubble using `Fragment` wrapper; find first AI message index

---

## Verification Process

### Step 1 — Identify the scope

```bash
git log --oneline @{u}..
```

Found 3 feature commits:
- `c807b76` — complete Cross-Session Continuity Summary frontend + close P0
- `0d8f25a` — add Cross-Session Continuity Summary backend
- `eacc5fc` — plan Cross-Session Continuity Summary

Full diff stat: 21 files changed, 504 insertions, 127 deletions (includes prior P0 work).

### Step 2 — Check for verifier skills

```bash
ls .claude/skills/
```

No `.claude/skills/` directory — cold start from scratch.

### Step 3 — Confirm app is running

```bash
docker compose -f docker/docker-compose.yml ps
```

All services up. `docker-api-1` and `docker-frontend-1` both running on ports 8000 and 3000.

### Step 4 — Initial Playwright test (inline `python3 -c`)

Confirmed frontend loads (HTTP 200, title "NIM AI Gateway"). Identified that the chat input uses `input[placeholder="Ask anything…"]` (not a `textarea`). Identified `button:has-text("+ New Chat")` for starting fresh conversations.

**Note:** Playwright scripts written to `/tmp/` files failed with `ERR_CONNECTION_REFUSED` — the file-based execution runs in a sandboxed environment without localhost network access. All Playwright execution had to use inline `python3 -c "..."` via the Bash tool.

### Step 5 — Direct SSE test (first attempt — stale container)

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token ...)
curl -s -N --max-time 30 -X POST http://localhost:8000/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"say hi","conversation_id":null}' | grep '"type":"done"'
```

**Finding:** The `done` event did NOT contain a `last_session` field at all:
```json
{"type":"done","model":"meta/llama-3.1-8b-instruct","cache_hit":false,...,"src_count":0,"conversation_id":"bceaa6e3-..."}
```

`query_type`, `src_count`, and `provenance` were present (added just above `last_session` in `stream.py`), but `last_session` was completely absent. This meant either the code wasn't executing line 327, or the container wasn't running the new code at all.

### Step 6 — Diagnose: stale container

Compared image build time against commit timestamps:

```bash
git log --format="%h %ai %s" -5
docker images docker-api --format='{{.CreatedAt}}'
```

**Result:**
- Docker image built: `2026-05-29 20:22:18 +0800` (12:22 UTC)
- Feature commits: `01:40–02:07 +0800` (17:40–18:07 UTC next day)
- **The image was ~6 hours behind the commits.** The entire Cross-Session feature was undeployed.

### Step 7 — Rebuild and restart

```bash
docker compose -f docker/docker-compose.yml build api frontend
docker compose -f docker/docker-compose.yml up -d api frontend
```

Both images rebuilt and containers restarted. Both services returned HTTP 200 after restart.

### Step 8 — Re-test SSE stream (after rebuild)

Same curl command as Step 5. **Result:**
```json
{"type":"done",...,"last_session":"Last session: \"User says hi, AI responds.\" — 1 minutes ago","conversation_id":"33fcc196-..."}
```

Backend correctly generates and emits `last_session`. The `—` is the em dash (`—`) from the format string.

### Step 9 — UI verification via Playwright

Logged in as `user`, clicked `+ New Chat`, typed `Say hi`, pressed Enter. Watched for `✦` character in page content.

**Result:** Banner appeared at 0.5s (first poll after message arrived). Banner text extracted from DOM:

```
✦ Last session: "User says hi, AI responds." — 1 minutes ago
```

Screenshot saved: `/tmp/02_banner.png`

### Step 10 — Auto-dismiss test

After banner appeared, polled every 500ms for absence of `✦`.

**Result:** Banner disappeared at exactly ~8.0s after appearing.

Screenshot saved: `/tmp/03_dismissed.png`

### Step 11 — Probes

**Probe 1: Banner should NOT appear when replying to an existing conversation.**

Clicked an existing conversation in the sidebar, sent a message, waited 10s.

Result: No banner appeared. ✅ (`last_session` is only populated when `req.conversation_id` is null in the backend; existing conversations send their ID.)

**Probe 2: Second message in same new conversation should not re-show banner.**

Started new conversation, sent first message, waited for banner, then sent second message.

Result: Banner cleared immediately on second send. ✅ (`conv.setLastSession('')` is called at the start of every send handler regardless of whether it's the first or a subsequent message.)

**Probe 3: Zero prior conversations (code path, not live).**

All seeded users had existing conversations by the time probes ran, so a live zero-conv test was not possible. Code path verified: `helpers.py` line `if ls_row and ls_row.title:` correctly guards the case — no `ls_row` means `last_session` stays `""`.

---

## Verdict

**PASS**

The feature works correctly end-to-end after container rebuild. The stale image deployment gap would have left the feature completely invisible in a production environment.

---

## Findings

**⚠️ Plural grammar bug:** `helpers.py` always uses `"minutes"` (plural) even for 1-minute gaps: `"1 minutes ago"`. Should branch on `int(elapsed.total_seconds() / 60) == 1` to emit `"1 minute ago"`. Minor cosmetic issue.

**⚠️ Deploy gap detected and fixed:** Docker images were ~6 hours stale at time of verification. The `docker-api` image build timestamp (`20:22 +0800`) predated all three Cross-Session commits (`01:40–02:07 +0800` the following morning). A production deploy without rebuild would have shipped the feature invisible. Rebuilt as part of verification.

**🔍 Playwright file-based scripts do not have localhost access:** `python3 /tmp/script.py` runs in a sandboxed env without network access to `localhost`. All Playwright execution must use inline `python3 -c "..."` via Bash. This is a session-environment constraint, not a project issue.

**🔍 Zero-conv path not exercised live:** All users accumulated conversations before the no-prior-conversations scenario could be tested. Code is provably correct from inspection but not observable at runtime in this session.
