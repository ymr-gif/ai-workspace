# NIM AI Gateway

A self-hosted AI chat platform backed by NVIDIA NIM inference. Multi-model routing, hybrid RAG, persistent graph memory, and an AI agent tool loop — all in a single Docker Compose stack.

**Backend:** Python / FastAPI · **Frontend:** React / Vite · **Infra:** PostgreSQL + pgvector, Redis, Neo4j, Prometheus, Grafana

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  (React / Vite)                                    │
│  14 panels · 13 hooks · SSE streaming                      │
└────────────────────────┬────────────────────────────────────┘
                         │  REST + SSE
                    nginx proxy
                         │
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI  (uvicorn, async)                                  │
│                                                             │
│  Keyword Router ──► NIM API                                 │
│    llama 8B / DeepSeek coder / llama 70B                   │
│    fallback chain · circuit breaker · retry/jitter         │
│                                                             │
│  RAG Pipeline                                               │
│    pgvector cosine + BM25 → RRF / weighted fusion          │
│    adaptive policy: factual · relational · temporal · broad │
│                                                             │
│  Memory Engine                                              │
│    compressed history · project summary · salience facts   │
│    conflict detection · preference extraction · compaction  │
│                                                             │
│  Graph Memory  ──► Neo4j                                    │
│    entity + relation extraction (70B) · 500 entity cap     │
│                                                             │
│  Agent Tool Loop (12 tools, max 60 iterations)             │
│    file I/O · fuzzy patch · graph query · memory write     │
│    web search · ask_user pause · identical-signature abort │
│                                                             │
│  Background (ARQ workers + APScheduler)                     │
│    embed · compact · insights · behavior profile · backup  │
└───────────┬───────────┬────────────┬────────────┬──────────┘
            │           │            │            │
       PostgreSQL     Redis        Neo4j     Prometheus
       + pgvector   (cache,      (entity      + Grafana
       + pgBouncer   rate limit,   graph)     (24 panels,
       40 migrations  circuit                  2 alerts)
       22 ORM models  breaker)
```

---

## Features

### Inference & Routing
- **Keyword classifier** automatically picks the right model for the task; supports per-request override and per-conversation model lock
- **Fallback chain**: `chosen model → reasoning → coder → llama` — never drops a request if a model is available
- **Circuit breaker**: 5 consecutive failures trip the circuit; 90s cooldown; Redis-persisted across restarts; pre-tripped at startup if a model probe fails
- **Retry with jitter**: up to 4 attempts with exponential + jitter backoff (~1s / 2s / 4s / 8s)
- **Rate limiting**: sliding-window per user (15 req/60s) + per model (llama=15, coder=10, reasoning=5); Redis-backed; fail-open when Redis is down

### Retrieval-Augmented Generation
- **Hybrid retrieval**: pgvector cosine similarity + PostgreSQL BM25 full-text, parallelised, fused via Reciprocal Rank Fusion (k=60) or weighted fusion with configurable α
- **Adaptive query policy**: classifies each query as `factual` / `relational` / `temporal` / `broad` and selects the fusion strategy and k accordingly
- **File knowledge base**: upload PDF, DOCX, XLSX, plain text/code/markdown; streaming SHA-256 dedup; 1600-char chunks, 200-char overlap, sentence-aligned tail
- **Context budget allocator**: drops lowest-priority memory tiers when the prompt would exceed `context_window − max_output_tokens − 10%`; re-applied on every tool iteration

### Memory System
Memory is layered — injected in priority order on every turn:

```
system prompt → graph context → graph facts → user state → active goals
→ project summary → relevant chunks → earlier history → last session
→ conversation history → file context → user message
```

- **Compressed history**: summarised when conversation exceeds 4 000 tokens or 15 messages
- **Project summary**: maintained separately; updated alongside history compression
- **Salience scoring**: per-fact `0.95^(hours/24)` time decay before top-20 selection; bumped on every access; facts below 0.05 pruned
- **Memory compaction**: LLM-driven dedup and merge; snapshots to `UserMemoryVersion`; scheduled daily at 03:00 UTC via APScheduler
- **Conflict resolution**: contradicting facts detected and stored as `MemoryConflict`; user resolves via keep A / keep B / merge / discard; auto-resolved `keep_a` after 7 days
- **Preference extraction**: runs every 50 assistant messages; no LLM inference cost per turn
- **Behavior profile**: lightweight per-reply counters (query types, topics, tools, models used); feeds proactive insight generation

### Graph Memory (Neo4j)
- Entity and relationship extraction by the 70B reasoning model after each reply
- Per-user knowledge graph with a 500-entity cap; LRU eviction by `updated_at`
- Graph query results Redis-cached (TTL 60s); cache busted on every write
- Fulltext index `entity_name_ft` + range index `entity_user_id` created on startup
- Batch UNWIND writes (2 round-trips regardless of entity/relation count)

### AI Agent Tool Loop
Activated when file IDs are attached to a request; forces the 70B model.

| Tool | Description |
|---|---|
| `list_files` | list knowledge base files |
| `read_file` | read up to 100k chars (capped to 12k in context) |
| `write_file` / `create_file` / `append_to_file` | file mutations |
| `patch_file` | fuzzy find-and-replace (exact → CRLF-norm → stripped-edges) |
| `search_in_file` / `search_across_files` | search without full reads |
| `ask_user` | pause the loop and ask the user a question; resumes on reply |
| `query_graph` | Cypher query against the user's Neo4j graph |
| `write_memory` | propose a memory write; requires user confirmation |
| `web_search` | search the web for live information; conditionally injected when `WEB_SEARCH_ENABLED=true` and query matches keyword heuristic; backends: SearXNG (self-hosted) or Tavily |

### Event-Driven Webhook Triggers
External systems can POST events to the platform via a per-user token:

```
POST /api/webhooks/{user_token}   { "event_type": "reminder", "payload": {...} }
```

Supported event types: `file.uploaded` · `reminder` · `external.data`

Each event is persisted as a `WebhookEvent` record, then an ARQ job generates a `UserInsight` from the payload. Users manage their token via:

```
GET    /auth/me/webhook-token   — retrieve current token (null if not yet generated)
POST   /auth/me/webhook-token   — generate / regenerate token
DELETE /auth/me/webhook-token   — revoke token
```

Guards: identical `(tool, args)` signature repeated → abort (writes after 3, reads after 8); hard cap at 60 iterations.

### Frontend
- **14 panels**: Sidebar, MessageList, ModelToolbar, FilesPanel, FileViewer, ToolLogPanel, UsagePanel, InsightsPanel, InvitePanel, MemoryPanel, SearchPanel, AutomationsPanel, GoalsPanel, SettingsModal
- **13 hooks**: dedicated hook per domain (`useStreamChat`, `useMemory`, `useFiles`, `useGoals`, etc.)
- **SSE streaming**: raw cursor → done → `<ReactMarkdown>`; per-bubble token count, cost, query type, source count, and cyan `web` badge (when `web_searched`)
- **Unified search**: fans out to files, conversations, memory, and graph; results grouped by source
- **Memory panel**: per-fact salience score bars, conflict resolution UI, interactive graph (ReactFlow circle layout with click-to-highlight)
- **Goals + Automations**: CRUD panels for user goals (with conversation linking) and scheduled prompts (cron + daily/weekly/monthly aliases)

### Observability
- **Activity trace**: every pipeline step (`cache → route → budget → model_call → fallback → tool`) timed, tagged with `level: error | info`, and persisted as JSONB on the assistant message
- **Prometheus + Grafana**: 24-panel dashboard, 2 automated alert rules (circuit breaker trip, success rate < 99%); TSDB persists across restarts via named volume
- **Prometheus multiprocess mode**: uvicorn workers share a tmpfs metric dir; `/metrics` endpoint aggregates via `MultiProcessCollector`
- **Structured logging** throughout; request ID (`X-Request-ID`) on every response

### Infrastructure
- **pgBouncer** in transaction mode: 200 max clients, 20 server connections; `AUTH_TYPE=plain` required for pg16
- **ARQ task queue**: 4 retry attempts with 5s / 30s / 120s backoff; per-job failure counter in Prometheus
- **Automated daily backup**: `pg_dump` → gzip → `storage/backups/`; configurable retention via `KEEP_DAYS`
- **39 Alembic migrations**, applied automatically on container start

### Auth & Admin
- JWT (HS256) + API key fallback; API keys stored as SHA-256 hex — plaintext never persisted
- bcrypt passwords; invite-gated registration; `is_active` gate on every request
- Per-user cost cap with rolling window (402 on exceed); admin audit log for all privileged actions
- Live `.env` management via `/admin/env` — masked values, atomic write, hot reload via `importlib.reload(config)`

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, Alembic |
| Frontend | React 18, Vite, ReactFlow |
| Database | PostgreSQL 16 + pgvector, pgBouncer |
| Cache | Redis |
| Graph | Neo4j 5 |
| Monitoring | Prometheus, Grafana |
| Task queue | ARQ |
| Scheduler | APScheduler |
| Runtime | Docker Compose |
| AI | NVIDIA NIM API |

---

## Models

| Role | Model | Env var |
|---|---|---|
| General | `meta/llama-3.1-8b-instruct` | `MODEL_LLAMA` |
| Coder | `deepseek-ai/deepseek-v4-flash` | `MODEL_CODER` |
| Reasoning | `meta/llama-3.3-70b-instruct` | `MODEL_REASONING` |
| Embedding | `nvidia/nv-embedqa-e5-v5` (1024d) | `MODEL_EMBEDDING` |

Model selection priority: `per-request override > conversation lock > keyword router`

---

## Quickstart

**Prerequisites:** Docker + Docker Compose, [NVIDIA NIM API key](https://build.nvidia.com/)

```bash
git clone https://github.com/ymr-gif/ai-workspace.git
cd ai-workspace
cp .env.example .env
```

Set the minimum required values in `.env`:

```env
NVIDIA_API_KEY=nvapi-...
JWT_SECRET_KEY=change-me-to-a-random-secret
```

```bash
cd docker && docker compose up -d
```

| Service | URL |
|---|---|
| Frontend | `http://localhost:3000` |
| API docs | `http://localhost:8000/docs` |
| Grafana | `http://localhost:3001` |
| Neo4j browser | `http://localhost:7474` |

Default seeded accounts: `admin / admin-secret` · `user / user-secret` — change these before any public exposure.

---

## API Reference

All endpoints require `Authorization: Bearer <token>` unless noted.

### Auth
```
POST /auth/token              login (form: username, password)
POST /auth/register           register (json: username, password, invite_token?)
POST /auth/me/api-key         generate API key (returned once, stored as hash)
DELETE /auth/me/api-key       revoke API key
```

### Chat
```
POST /chat/stream             SSE streaming (json: message, conversation_id?, model_override?, file_ids?, image_b64?)
POST /chat                    non-streaming
```

**SSE event types:** `token` · `tool_call` · `tool_result` · `status` · `ask_user` · `confirm_write_memory` · `proactive` · `preamble_discard` · `error` · `done`

`done` payload: `model` · `cache_hit` · `fallback_used` · `web_searched` · `total_tokens` · `prompt_tokens` · `completion_tokens` · `cost_usd` · `query_type` · `src_count` · `provenance[]` · `conversation_id` · `last_session?`

### Conversations
```
GET    /conversations                 list; ?q= full-text search
GET    /conversations/{id}/messages   message history with activity traces
PATCH  /conversations/{id}            update title or locked_model
DELETE /conversations/{id}
GET    /conversations/{id}/export     markdown export
```

### Files
```
POST /files/upload            multipart upload
GET  /files                   list with chunk status
GET  /files/{id}/content      raw content
PUT  /files/{id}/content      overwrite (saves version)
GET  /files/{id}/versions     version history
POST /files/{id}/restore/{v}  restore version
DELETE /files/{id}
```

### Memory & Graph
```
GET  /memory                          compressed memory + conflict count
POST /memory/write                    confirm a memory write (from agent)
GET  /memory/conflicts                list unresolved conflicts
POST /memory/conflicts/{id}/resolve   resolve: keep_a | keep_b | merge | discard_both
GET  /graph/stats
GET  /graph/sample?limit=&entity_type=
DELETE /graph/entities/{name}
POST /graph/prune
```

### Other
```
GET  /api/search?q=&scope=            unified search across all sources
GET  /usage                           aggregate token + cost stats
GET  /export/full                     ZIP: conversations + files + memory + graph
GET  /goals                           user goals
GET  /scheduled-prompts               automation schedules
POST /webhooks/{user_token}           receive external event (public — no auth header needed)
GET  /auth/me/webhook-token           retrieve webhook token
POST /auth/me/webhook-token           generate / regenerate webhook token
DELETE /auth/me/webhook-token         revoke webhook token
GET  /system/hardware                 CPU / RAM / GPU / disk / uptime
GET  /health
```

### Admin (role: admin)
```
GET    /admin/users
PATCH  /admin/users/{id}
POST   /admin/users/{id}/cost-limit
GET    /admin/audit-log
GET    /admin/env
PUT    /admin/env
POST   /admin/env/reload
POST   /admin/re-embed
```

---

## Configuration

See `.env.example` for all variables. Commonly changed:

| Variable | Default | Description |
|---|---|---|
| `NVIDIA_API_KEY` | — | NIM API key (required) |
| `JWT_SECRET_KEY` | — | JWT signing secret (required) |
| `DATABASE_URL` | — | PostgreSQL via pgBouncer |
| `REDIS_URL` | — | Redis connection string |
| `NEO4J_URI` | — | Bolt URI; omit to disable graph memory |
| `REQUIRE_INVITE` | `false` | Gate registration behind invite tokens |
| `REQUEST_TIMEOUT` | `30` | NIM request timeout (seconds) |
| `MAX_CONCURRENT_REQUESTS` | `10` | Max parallel NIM requests (cap 50) |
| `MODEL_LLAMA` | `meta/llama-3.1-8b-instruct` | Override general model |
| `MODEL_CODER` | `deepseek-ai/deepseek-v4-flash` | Override coder model |
| `MODEL_REASONING` | `meta/llama-3.3-70b-instruct` | Override reasoning model |
| `MODEL_EMBEDDING` | `nvidia/nv-embedqa-e5-v5` | Changing this triggers a full re-embed |
| `BACKUP_SCHEDULE` | `0 2 * * *` | Cron for automated DB backup |

---

## Project Structure

```
ai-api/
├── backend/
│   ├── api/                  route handlers (chat, files, conversations, memory, graph, admin, …)
│   ├── llm/
│   │   ├── service/          context builder, SSE stream, tool loop
│   │   ├── retriever/        hybrid RAG (vector + BM25, fusion, adaptive policy)
│   │   ├── summarizer/       history compression, memory compaction
│   │   ├── graph_memory.py   Neo4j entity extraction + query
│   │   ├── router.py         keyword model classifier
│   │   └── tools/            11 agent tool schemas + executor
│   ├── auth/                 JWT, bcrypt, API key, invites
│   ├── models/               21 SQLAlchemy ORM models
│   ├── alembic/versions/     39 migrations
│   ├── services/             ARQ workers, file processor, scheduler
│   ├── observability/        Prometheus counters/histograms
│   └── tests/                47 tests (retrieval: mocked DB, no NIM)
├── frontend/
│   ├── src/
│   │   ├── components/Chat/  14 panel components
│   │   └── hooks/            13 domain hooks
│   └── public/canvas/        JARVIS ReactFlow workspace (static bundle)
└── docker/
    ├── docker-compose.yml
    ├── docker-compose.prod.yml
    ├── backend.Dockerfile
    ├── frontend.Dockerfile
    ├── nginx.conf / nginx.frontend.conf / nginx.prod.conf
    └── grafana/provisioning/ datasources, dashboards, alert rules
```

---

## License

MIT
