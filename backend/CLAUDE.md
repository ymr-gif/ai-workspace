# Backend Reference

## Structure
```
backend/
├── main.py                 ← thin app factory: lifespan, middleware, router includes (~83 lines)
├── config.py               ← env vars, REQUIRE_INVITE bool, MODEL_PRICING, _int_env()
├── models.py               ← ORM: User, File, FileChunk, FileVersion, Conversation, Message,
│                              UserMemory, MessageEmbedding, UserMemoryVersion, ConversationFile,
│                              ToolCallLog, PromptTemplate, ScheduledPrompt, ScheduledPromptRun,
│                              Workspace, WorkspaceMemory, Invitation, UserInsight, AdminAuditLog
│                              Conversation.workspace_id UUID FK → workspaces SET NULL
│                              File.workspace_id UUID FK → workspaces SET NULL  (was String 64)
│                              Message.content_tsv tsvector GENERATED (GIN indexed) — full-text search
│                              User: is_active, cost_limit_usd (NULL = no cap), cost_window_days (NULL = all-time), api_key
│                              File: sha256_hash (String 64, nullable, indexed) — dedup key
│                              UserInsight: id UUID, user_id, content, is_read, created_at
│                              AdminAuditLog: id UUID, admin_id, action (str64), target_user_id, detail JSONB, created_at
├── create_user.py          ← seeds admin/user accounts
├── alembic/versions/
│   ├── 001–007             ← conversations, memory, embeddings, project summary, versioning, model control
│   ├── 008_file_knowledge.py  ← file_chunks vector(1024) + HNSW + conversation_files
│   ├── 009_file_versions.py   ← file_versions table
│   ├── 010_tool_call_log.py   ← tool_call_logs (id, user_id, conversation_id, tool_name, args JSONB, result_preview)
│   ├── 011_token_usage.py     ← prompt_tokens, completion_tokens, total_tokens, cost_usd on messages
│   ├── 012_cost_caps.py       ← cost_limit_usd (Float, nullable) on users
│   ├── 013_hybrid_search.py   ← pg_trgm; content_tsv tsvector GENERATED ALWAYS AS STORED + GIN index on file_chunks
│   ├── 014_prompt_templates.py ← prompt_templates table
│   ├── 015_scheduled_prompts.py ← scheduled_prompts + scheduled_prompt_runs tables
│   ├── 016_file_dedup.py      ← sha256_hash (String 64) + ix_files_user_sha256 on files
│   ├── 017_bm25_simple_config.py ← recreates content_tsv on file_chunks + message_embeddings with 'simple' config
│   ├── 018_workspaces.py      ← workspaces table; files.workspace_id String→UUID FK; conversations.workspace_id
│   ├── 019_workspace_memory.py ← workspace_memory table (1:1 with workspaces)
│   ├── 020_message_search.py  ← messages.content_tsv GENERATED tsvector + GIN index
│   ├── 021_invitations.py     ← invitations table (token, created_by, used_by, expires_at)
│   ├── 022_api_key.py         ← api_key (String 64, unique, nullable) + index on users
│   ├── 023_user_insights.py   ← user_insights table
│   ├── 024_admin_audit_log.py ← admin_audit_logs table (4 indexes)
│   └── 025_cost_window.py     ← cost_window_days (Integer, nullable) on users
├── auth/
│   ├── router.py           ← /auth/token, /register (+ invite token validation + Default workspace creation), /me
│   ├── invites.py          ← /auth/invite (admin: generate token), /auth/invites (admin: list)
│   ├── security.py         ← JWT, bcrypt, get_current_user, require_role
│   └── schemas.py          ← Token, TokenData, RegisterRequest (+ invite_token field)
├── llm/
│   ├── service/            ← PACKAGE (was single service.py)
│   │   ├── __init__.py     ← re-exports: generate_stream, compare_streams, build_context_messages
│   │   ├── context.py      ← build_context_messages() + _needs_file_tools() + _FILE_OP_KEYWORDS
│   │   │                      workspace_memory injected as [WORKSPACE STATE] between USER/PROJECT STATE
│   │   ├── stream.py       ← generate_stream(), generate_response(), MAX_TOOL_ITERATIONS=10
│   │   │                      workspace_memory param → passed to build_context_messages
│   │   │                      model priority: image → model_override → file tools (70B) → router
│   │   └── compare.py      ← compare_streams()
│   ├── nim.py              ← call() + call_stream() → NIM API
│   │                          call_stream() accumulates tool_call deltas, yields {"__tool_calls__": [...]}
│   │                          yields {"__usage__": {prompt_tokens, completion_tokens, total_tokens}}
│   │                          stream_options:{include_usage:true} on every request
│   ├── tools.py            ← TOOL_SCHEMAS (9 tools) + execute_tool() dispatcher
│   │                          ASK_USER_PREFIX = "__ASK_USER__:"
│   │                          Every execute_tool() logs to ToolCallLog via db.flush()
│   ├── router.py           ← classify() keyword matching, route()
│   ├── circuit_breaker.py  ← is_open(), record_failure(), record_success()
│   ├── client.py           ← shared httpx.AsyncClient + semaphore
│   ├── embeddings.py       ← embed(text, input_type) → list[float]
│   ├── retriever.py        ← retrieve(), retrieve_global(), get_relevance_scores(message_ids=),
│   │                          store_exchange(), retrieve_from_files(), _rrf_merge() (k=60)
│   │                          All retrieve*() accept query_text for BM25 hybrid side
│   │                          _FETCH_N=20 per side; graceful fallback to pure vector
│   └── summarizer.py       ← update_memory(), compress_history(), update_project_summary()
│                              _update_memory() also calls _update_workspace_memory() after UserMemory update
├── cache/
│   ├── cache.py            ← Redis primary + in-memory LRU fallback
│   │                          get/set accept model, history_tail, system_prompt kwargs → context-aware key
│   ├── keys.py             ← normalize(), make_key(message, *, model, history_tail, system_prompt) → SHA256 hex
│   │                          CACHE_VERSION="v2"; all 4 fields hashed; old v1 keys ignored naturally
│   └── memory.py           ← OrderedDict LRU, max 1000 entries
├── core/
│   ├── db.py               ← engine, get_db, init_db
│   │                          pool_size=5, max_overflow=10, pool_pre_ping=False
│   │                          connect_args={"prepared_statement_cache_size": 0}
│   │                          (pgBouncer transaction mode — prepared stmts can't cross connections)
│   ├── redis_client.py     ← singleton async Redis
│   ├── arq_pool.py         ← singleton ARQ job pool; init_arq_pool() called in main.py lifespan
│   └── logger.py           ← setup_logging(), JSON or plain formatter
├── rate_limiter/
│   └── rate_limiter.py     ← Redis sliding-window, fail-open; limit(n, window, key) dependency
│                              check_model_rate(full_model_name, username) — imperative per-model limit
│                              key: rate:model:{key}:user:{username}; fails open on Redis error
├── observability/
│   ├── prom_metrics.py     ← all Prometheus counters/histograms
│   ├── metrics.py          ← record_* wrappers
│   ├── metrics_api.py      ← reads live from Prometheus objects
│   ├── metrics_worker.py   ← standalone worker container
│   ├── stream.py           ← emit() Redis Stream writer
│   ├── file_metrics.py     ← record_upload(), record_delete(), record_chunks(n), record_tool_call(name)
│   └── token_metrics.py    ← record_tokens(model, prompt, completion, cost)
├── api/
│   ├── chat/               ← package; main.py: from api.chat import router
│   │   ├── schemas.py      ← ChatRequest: message, conversation_id, workspace_id, model_override,
│   │   │                      temperature, max_tokens, top_p, compare, image_b64, image_mime_type
│   │   ├── helpers.py      ← _resolve_model, _estimate_tokens, _embed_exchange, _auto_title,
│   │   │                      _resolve_conversation (assigns workspace; falls back to Default),
│   │   │                      _build_stream_context (loads WorkspaceMemory + workspace system_prompt),
│   │   │                      _check_cost_cap (rolling window via cost_window_days; label in error),
│   │   │                      _extract_model_params, _calculate_tokens_and_cost
│   │   └── router.py       ← /chat + /chat/stream; calls check_model_rate() after effective_model resolved
│   │                          auto-title after 2nd message; workspace system_prompt merge
│   ├── workspaces.py       ← full workspace CRUD + memory routes (prefix /workspaces)
│   │                          POST /workspaces, GET /workspaces (+ conv/file counts),
│   │                          GET/PATCH/DELETE /{id}, GET /{id}/conversations, GET /{id}/files,
│   │                          GET /{id}/memory, PUT /{id}/memory
│   ├── files/              ← package; prefix="/files"
│   │   ├── utils.py        ← _file_dict(), _get_file_or_404(), logger, storage, MAX_FILE_SIZE
│   │   ├── router.py       ← upload (rate 20/60), list, delete, content, status, download,
│   │   │                      rename, put_content; sha256 dedup before DB insert
│   │   ├── ingest.py       ← /ingest-url (rate 10/60); sha256 dedup on extracted text
│   │   ├── workspaces.py   ← GET /workspaces (returns [{id,name}] from Workspace table),
│   │   │                      PATCH /{id}/workspace (accepts UUID, validates ownership)
│   │   ├── versions.py     ← /{id}/versions, /{id}/versions/{vid}, restore
│   │   └── stream.py       ← /{id}/status/stream — SSE; polls DB + Redis every 0.8s
│   ├── conversations.py    ← conversation routes; ?workspace_id= filter; ?q= full-text search;
│   │                          GET /{id}/export?format=markdown|json; messages returns token fields
│   ├── memory.py           ← memory routes
│   ├── system.py           ← /health (pings NIM, embedding, Redis concurrently), /metrics
│   ├── tool_logs.py        ← GET /tool-calls?limit=&conversation_id=
│   ├── admin.py            ← require_role("admin"); users CRUD, usage, cost-limit, audit-log
│   │                          _audit(db, admin, action, target_user_id, detail) — written in same commit
│   │                          Actions logged: user.active.enabled/disabled, user.cost_limit.set/removed
│   │                          CostLimitRequest: cost_limit_usd + cost_window_days (default 30, None=all-time)
│   │                          GET /admin/audit-log?limit&offset&action&target_user_id
│   ├── templates.py        ← CRUD for prompt templates + /apply/{conversation_id}
│   ├── scheduled_prompts.py ← CRUD + run history + manual trigger
│   └── usage.py            ← GET /usage, GET /usage/history
├── services/
│   ├── processor.py        ← extract_text(), chunk_text(), process_file_async()
│   │                          process_file_async(): enqueues ARQ job if pool available; inline fallback
│   │                          Semantic chunker: paragraph → sentence → word split
│   │                          CHUNK_SIZE=1600, OVERLAP=200; tail sentence-aligned via regex
│   │                          asyncio.gather(*[embed(c) for c in chunks]) — concurrent embedding
│   │                          Redis proc_progress:{file_id} (0.0→1.0); deleted on completion
│   ├── arq_worker.py       ← ARQ WorkerSettings + process_file_job()
│   │                          max_tries=4; retries at 5s, 30s, 120s; marks error on final failure
│   ├── file_service.py     ← write_content, append_content, patch_content, restore_version
│   │                          _fuzzy_replace: exact → normalized \r\n → stripped edges (3-pass)
│   │                          save_version() called before every mutation
│   └── scheduler_worker.py ← APScheduler cron runner; saves output as File → process_file_async
├── storage/
│   └── storage_manager.py  ← save_file() → (path, filename, size_bytes, sha256_hex) 4-tuple
│                              save_text() → (path, size_bytes, sha256_hex) 3-tuple
│                              SHA256 computed while streaming (no second read pass)
└── tests/
    └── test.py             ← 21 pytest unit tests
```

---

## API Routes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/chat` | JWT | Non-streaming chat |
| POST | `/chat/stream` | JWT | SSE streaming |
| GET | `/memory` | JWT | memory sheet + project summary |
| PUT | `/memory` | JWT | manual edit (snapshots version) |
| GET | `/memory/export` | JWT | JSON download |
| POST | `/memory/import` | JWT | overwrite from JSON |
| GET | `/memory/history` | JWT | last 10 UserMemoryVersion snapshots |
| GET | `/health` | none | per-check {status, latency_ms} |
| GET | `/metrics` | none | Prometheus export |
| POST | `/auth/token` | none | login → JWT |
| POST | `/auth/register` | none | register user |
| GET | `/auth/me` | JWT | current user (includes `has_api_key`) |
| POST | `/auth/me/api-key` | JWT | generate API key |
| DELETE | `/auth/me/api-key` | JWT | revoke API key |
| POST | `/v1/chat/completions` | JWT or API key | OpenAI-compatible chat (streaming + non-streaming) |
| POST | `/files/upload` | JWT | upload → background process |
| GET | `/files` | JWT | list (?workspace_id=) |
| DELETE | `/files/{id}` | JWT | delete file + chunks + disk |
| POST | `/files/ingest-url` | JWT | fetch URL → chunk+embed |
| GET | `/files/search` | JWT | `?q=&workspace_id=&top_k=` hybrid file search → [{file_id, filename, chunk}] |
| GET | `/files/workspaces` | JWT | workspace list [{id,name}] for files panel |
| PATCH | `/files/{id}/workspace` | JWT | assign workspace (UUID) |
| GET | `/files/{id}/content` | JWT | full text |
| GET | `/files/{id}/status` | JWT | one-shot poll |
| GET | `/files/{id}/status/stream` | JWT | SSE until ready/error |
| GET | `/files/{id}/download` | JWT | FileResponse |
| PATCH | `/files/{id}/rename` | JWT | rename |
| PUT | `/files/{id}/content` | JWT | overwrite; saves version |
| GET | `/files/{id}/versions` | JWT | last 50 desc |
| GET | `/files/{id}/versions/{vid}` | JWT | single version |
| POST | `/files/{id}/versions/{vid}/restore` | JWT | restore version |
| POST | `/workspaces` | JWT | create workspace |
| GET | `/workspaces` | JWT | list (+ conv/file counts) |
| GET | `/workspaces/{id}` | JWT | single workspace |
| PATCH | `/workspaces/{id}` | JWT | update name/description/system_prompt |
| DELETE | `/workspaces/{id}` | JWT | delete (orphans content) |
| GET | `/workspaces/{id}/conversations` | JWT | conversations in workspace |
| GET | `/workspaces/{id}/files` | JWT | files in workspace |
| GET | `/workspaces/{id}/memory` | JWT | workspace memory sheet |
| PUT | `/workspaces/{id}/memory` | JWT | edit workspace memory |
| POST | `/auth/invite` | JWT (admin) | generate invite token (7-day expiry) |
| GET | `/auth/invites` | JWT (admin) | list all invitations |
| GET | `/conversations` | JWT | list; ?workspace_id= filter; ?q= full-text search |
| GET | `/conversations/{id}/messages` | JWT | messages + token fields |
| GET | `/conversations/{id}/export` | JWT | ?format=markdown|json download |
| PATCH | `/conversations/{id}` | JWT | memory_enabled / system_prompt / locked_model / workspace_id |
| DELETE | `/conversations/{id}` | JWT | delete |
| GET | `/conversations/{id}/files` | JWT | attached files |
| POST | `/conversations/{id}/files` | JWT | attach file |
| DELETE | `/conversations/{id}/files/{file_id}` | JWT | detach |
| GET | `/tool-calls` | JWT | ToolCallLog; ?limit=&conversation_id= |
| GET | `/usage` | JWT | own aggregate |
| GET | `/usage/history` | JWT | per-conversation (last 50) |
| GET | `/admin/users` | JWT (admin) | all users + usage (includes cost_window_days) |
| GET | `/admin/users/{id}/usage` | JWT (admin) | per-conversation breakdown |
| PATCH | `/admin/users/{id}/active` | JWT (admin) | toggle is_active; logs audit entry |
| PATCH | `/admin/users/{id}/cost-limit` | JWT (admin) | set cost_limit_usd + cost_window_days; logs audit entry |
| GET | `/admin/audit-log` | JWT (admin) | paginated audit log; ?action=&target_user_id=&limit=&offset= |
| POST | `/templates` | JWT | create template |
| GET | `/templates` | JWT | list own + shared |
| GET | `/templates/{id}` | JWT | single |
| PUT | `/templates/{id}` | JWT | update (owner) |
| DELETE | `/templates/{id}` | JWT | delete |
| POST | `/templates/{id}/apply/{conv_id}` | JWT | set conv system_prompt |
| POST | `/scheduled-prompts` | JWT | create |
| GET | `/scheduled-prompts` | JWT | list own |
| GET | `/scheduled-prompts/{id}` | JWT | single + recent runs |
| PATCH | `/scheduled-prompts/{id}` | JWT | update |
| DELETE | `/scheduled-prompts/{id}` | JWT | delete |
| POST | `/scheduled-prompts/{id}/run` | JWT | manual trigger |
| GET | `/scheduled-prompts/{id}/runs` | JWT | run history (last 20) |
| GET | `/metrics/overview` | none | Redis Streams stats |
| GET | `/metrics/models` | none | per-model breakdown |
| GET | `/metrics/latency` | none | latency percentiles |

---

## ChatRequest Fields
```python
message:          str          # required, max 2000 chars
conversation_id:  str | None
workspace_id:     str | None   # UUID; used when creating new conversation
model_override:   str | None   # short key or full model ID
temperature:      float | None # 0.0–2.0
max_tokens:       int | None   # 1–4096
top_p:            float | None # 0.0–1.0
compare:          bool         # all 3 models concurrently
image_b64:        str | None   # base64 image (~1.5MB limit) → forces MODEL_VISION
image_mime_type:  str | None   # "image/jpeg" | "image/png" | "image/webp"
```

---

## AI Agent Tool Loop

### Flow
```
user message + file_ids
  → _needs_file_tools(message) — skip tools for conversational messages
  → forces MODELS["reasoning"] (70B only reliable tool caller)
  → nim.py yields {"__tool_calls__": [...]} on finish_reason=="tool_calls"
  → execute_tool() → logs to ToolCallLog
  → yield SSE {type:"tool_call"} + {type:"tool_result"}
  → loop continues (max 10 iterations)
  → ask_user: yield {type:"ask_user"} + done → return
```

### Tools (`llm/tools.py`)
| Tool | Args | What it does |
|------|------|--------------|
| `list_files` | — | Files attached to conversation |
| `read_file` | file_id | Full text, cap 100k chars |
| `write_file` | file_id, content | Overwrite → re-embed |
| `create_file` | name, content | New file → attach → process |
| `append_to_file` | file_id, content | Append `\n\n` → re-embed |
| `patch_file` | file_id, old_text, new_text | Fuzzy find-replace → re-embed |
| `search_in_file` | file_id, query | Semantic top-10 chunks |
| `search_across_files` | query | Semantic top-10 across all attached |
| `ask_user` | question | Pause loop, amber card in UI |

### Guards
- Keyword heuristic: tools only if message contains file-op words
- Repetition: same tool >3× per turn → abort
- Iteration cap: MAX_TOOL_ITERATIONS = 10

---

## Memory System

### Context Injection Order
```
1. workspace system_prompt (if set) merged with conv system_prompt; file list with IDs
2. [USER STATE]       ← UserMemory.content
3. [WORKSPACE STATE]  ← WorkspaceMemory.content  (NEW)
4. [PROJECT STATE]    ← UserMemory.project_summary
5. [RELEVANT CONTEXT] ← pgvector cosine top-K
6. [EARLIER IN CONV]  ← history_summary
7. last 10 importance-weighted messages
8. [FILE CONTEXT]     ← cosine top-5 chunks (LAST — recency bias)
9. current user message
```

### Workspace System Prompt
- Workspace system_prompt takes precedence over conversation system_prompt
- If both set: merged as `ws_sysprompt + "\n\n" + conv_sysprompt`
- Workspace system_prompt also passed to compare mode

### Triggers
- Memory sheet: >3000 tokens OR every 10 assistant messages
- Project summary: >4000 tokens OR every 15 messages
- History compression: compresses all_msgs[:-10] → max 200 words
- WorkspaceMemory: updated alongside UserMemory when conv belongs to a workspace
- Lock: `pg_advisory_xact_lock(user_id)` prevents version races
- Auto-title: fires after 2nd message (all_count == 2) via `asyncio.create_task(_auto_title(...))`
  - Calls MODELS["llama"] with "Summarize in 6 words or fewer"

### Retrieval
- HNSW `vector_cosine_ops`, 1024d; normal top_k=3, reference top_k=8
- Hybrid: vector + BM25 (`websearch_to_tsquery`) merged via RRF (k=60)
- `content_tsv` generated column on `message_embeddings` — GIN index
- `get_relevance_scores()` accepts `message_ids` — filters to candidate set only

---

## Files & Knowledge

### Upload Pipeline
1. POST /files/upload → compute SHA256 while streaming
2. Check `(user_id, sha256_hash)` — if found: delete temp, return existing + `"duplicate": true`
3. Save → DB record → `process_file_async` background task
4. `extract_text()` → `chunk_text()` → `asyncio.gather` all embeddings → save FileChunk rows
5. Status: `uploaded` → `processing` → `ready` (or `error`)
6. Supported: PDF, DOCX (+ tables), Excel XLSX/XLS, plain text/code/markdown

### File Service (`services/file_service.py`)
- `write_content`: save_version → write → delete chunks → commit → re-embed
- `append_content`: save_version → append `\n\n` → delete chunks → commit → re-embed
- `patch_content`: read → fuzzy_replace → save_version → write → re-embed
- `restore_version`: get FileVersion → call write_content(v.content)
- `_fuzzy_replace`: exact → `\r\n` normalized → stripped edges (3-pass)

### Hybrid File Retrieval
- `retrieve_from_files()`: vector + BM25 parallel → RRF merge
- `content_tsv` generated column on `file_chunks` — GIN index, zero maintenance
- Falls back to pure vector if BM25 returns nothing

### Processing Status SSE
- Polls `db.refresh(f)` + Redis `proc_progress:{file_id}` every 0.8s
- Pushes `{id, status, progress?}` — terminates on `ready`/`error`

---

## Token Usage & Admin

### Token Tracking
- Real counts: NIM `stream_options:{include_usage:true}` → `{"__usage__": {...}}` → saved on Message
- Fallback: chars÷4 estimate if NIM returns no usage
- `cost_usd` = tokens × `MODEL_PRICING[model]` rates

### Model Pricing (`config.py:MODEL_PRICING`) — verify at build.nvidia.com
| Model | Input $/1M | Output $/1M |
|-------|-----------|------------|
| `meta/llama-3.1-8b-instruct` | $0.10 | $0.10 |
| `deepseek-ai/deepseek-v4-flash` | $0.20 | $0.60 |
| `meta/llama-3.3-70b-instruct` | $0.77 | $0.77 |

### Admin
- `PATCH /admin/users/{id}/active` — immediate block (get_current_user checks is_active); logs audit
- `PATCH /admin/users/{id}/cost-limit` — 402 when rolling-window spend ≥ limit; logs audit
  - `cost_window_days`: number of days in rolling window (null = all-time); default 30
  - `_check_cost_cap` adds `WHERE messages.created_at >= now() - interval` when window set
  - Error message includes window label: e.g. `$4.23 / $5.00 30d`
- `GET /admin/audit-log` — audit trail; filterable by action/target_user_id; paginated
  - Actions: `user.active.enabled`, `user.active.disabled`, `user.cost_limit.set`, `user.cost_limit.removed`
  - detail JSONB includes username + prev/new values
- Self-disable blocked

---

## Prometheus Metrics
| Metric | Type | Labels | Where |
|--------|------|--------|-------|
| `api_requests_total` | Counter | `status` | `api/chat/router.py` |
| `api_errors_total` | Counter | `type` | `api/chat/router.py` |
| `cache_hits_total` | Counter | — | `cache.py` |
| `cache_misses_total` | Counter | — | `cache.py` |
| `cache_writes_total` | Counter | — | `cache.py` |
| `model_usage_total` | Counter | `model` | `api/chat/router.py` |
| `model_latency_seconds` | Histogram | `model` | `api/chat/router.py` |
| `request_latency_seconds` | Histogram | — | `api/chat/router.py` |
| `ai_request_latency_seconds` | Histogram | — | `api/chat/router.py` |
| `fallback_total` | Counter | — | `service.py` |
| `circuit_breaker_trips_total` | Counter | — | `metrics.py` |
| `file_uploads_total` | Counter | — | `api/files/router.py` |
| `file_deletes_total` | Counter | — | `api/files/router.py` |
| `file_chunks_total` | Counter | — | `services/processor.py` |
| `file_tool_calls_total` | Counter | `tool` | `services/file_service.py` |
| `tokens_prompt_total` | Counter | `model` | `observability/token_metrics.py` |
| `tokens_completion_total` | Counter | `model` | `observability/token_metrics.py` |
| `tokens_total` | Counter | `model` | `observability/token_metrics.py` |
| `estimated_cost_usd_total` | Counter | `model` | `observability/token_metrics.py` |

---

## Possible Next Features
Suggestions only — ask for specs before implementing any.

### Reliability (DONE)
- **Persistent task queue (ARQ)** — `services/arq_worker.py` + `core/arq_pool.py`. API enqueues jobs to Redis; `arq-worker` Docker service consumes them. Survives restarts. `process_file_async()` falls back to inline if pool not available (scheduler_worker).
- **File processing retry** — ARQ `process_file_job` retries 3× at 5s/30s/120s backoff (`max_tries=4`). Final failure marks `upload_status="error"`.
- **DB in health check** — `GET /health` now includes `"db": {status, latency_ms}` via `SELECT 1` with 2s timeout.

### Agency Layer (DONE)
- **Proactive suggestions** — `llm/agency.py:generate_proactive_suggestion()`. After each chat response, llama generates a 1-sentence action hint. Emitted as `{type: "proactive", content: "..."}` SSE event before `done`. Uses `max_tokens=35`.
- **Background insight engine** — `generate_insight_job` in `arq_worker.py`. Enqueued every 10 assistant messages per user. Reads memory + recent messages → llama generates pattern/gap insight → stored in `user_insights` table. Max 3 unread per user.
- **Insights API** — `GET /insights` (unread by default, `?all=true`), `PATCH /insights/{id}/read`, `DELETE /insights/{id}`.
- **UserInsight model** — `user_insights` table (id UUID, user_id, content, is_read, created_at). Migration 023.

### New Capabilities (DONE)
- **OpenAI-compatible endpoint** — `POST /v1/chat/completions` in `api/compat.py`. Maps OpenAI model names (gpt-4→reasoning, gpt-3.5-turbo→llama). Streaming + non-streaming. Auth: JWT or API key. Works with LangChain/Open WebUI.
- **API key auth** — `api_key` (String 64, nullable) on `User` (migration 022). `POST /auth/me/api-key` generates key; `DELETE /auth/me/api-key` revokes. `auth/security.py` tries JWT first, falls back to DB key lookup.
- **Standalone file search** — `GET /files/search?q=&workspace_id=&top_k=` in `api/files/search.py`. Hybrid vector+BM25 RRF merge. Returns `[{file_id, filename, chunk}]`.

### Cost / Performance (DONE)
- **Streaming response cache** — `cache/keys.py` v2 key includes `(message, model, history_tail[-4 msgs], system_prompt)`. `use_cache` no longer requires empty history or no model_override — only excluded when file_chunks/image_b64/model_params present. Identical exchanges in identical context now cache. CACHE_VERSION bumped to v2; old v1 entries expire naturally.
- **Per-model rate limits** — `rate_limiter/rate_limiter.py:check_model_rate(full_model, username)`. Limits: llama=15, coder=10, reasoning=5 req/60s. Configurable via `RATE_LIMIT_LLAMA/CODER/REASONING` env. Only applies when user explicitly selects a model (model_override or locked_model). Auto-routed requests only hit global 15/60s limit.

### Admin / Observability (DONE)
- **Admin audit log** — `AdminAuditLog` model + migration 024. `_audit()` helper in `api/admin.py` commits alongside main change. `GET /admin/audit-log` with action/user filter + pagination. Actions: user.active.enabled/disabled, user.cost_limit.set/removed.
- **Rolling cost window** — `cost_window_days` (Integer, nullable) on User + migration 025. `_check_cost_cap` in `helpers.py` applies `WHERE created_at >= cutoff` when set. Default 30 days. `PATCH /admin/users/{id}/cost-limit` body accepts `cost_window_days`.
