# Backend Reference

## Structure
```
backend/
├── main.py                 ← thin app factory: lifespan, middleware, router includes (~83 lines)
├── config.py               ← env vars, startup guards, _int_env(); MODEL_EMBEDDING, NIM_EMBEDDING_URL
├── models.py               ← ORM: User, File, FileChunk, FileVersion, Conversation, Message,
│                              UserMemory, MessageEmbedding, UserMemoryVersion, ConversationFile,
│                              ToolCallLog, PromptTemplate, ScheduledPrompt, ScheduledPromptRun
│                              Message: prompt_tokens, completion_tokens, total_tokens, cost_usd
│                              User: is_active (checked in get_current_user — blocks immediately)
│                              User: cost_limit_usd (Float, nullable — NULL = no cap)
│                              File: sha256_hash (String 64, nullable, indexed) — dedup key
├── create_user.py          ← seeds admin/user accounts
├── alembic/versions/
│   ├── 001–007             ← conversations, memory, embeddings, project summary, versioning, model control
│   ├── 008_file_knowledge.py  ← file_chunks vector(1024) + HNSW + conversation_files
│   ├── 009_file_versions.py   ← file_versions table
│   ├── 010_tool_call_log.py   ← tool_call_logs (id, user_id, conversation_id, tool_name, args JSONB, result_preview)
│   ├── 011_token_usage.py     ← prompt_tokens, completion_tokens, total_tokens, cost_usd on messages
│   ├── 012_cost_caps.py       ← cost_limit_usd (Float, nullable) on users
│   ├── 013_hybrid_search.py   ← pg_trgm; content_tsv tsvector GENERATED ALWAYS AS STORED + GIN index
│   ├── 014_prompt_templates.py ← prompt_templates table
│   ├── 015_scheduled_prompts.py ← scheduled_prompts + scheduled_prompt_runs tables
│   └── 016_file_dedup.py      ← sha256_hash (String 64) + ix_files_user_sha256 on files
├── auth/
│   ├── router.py           ← /auth/token, /register, /me
│   ├── security.py         ← JWT, bcrypt, get_current_user, require_role
│   └── schemas.py          ← Token, TokenData, RegisterRequest
├── llm/
│   ├── service.py          ← generate_stream(), compare_streams(), build_context_messages()
│   │                          _needs_file_tools(message) — keyword heuristic, guards tool pass
│   │                          tool_call_counts guard: abort if same tool called >3 times/turn
│   │                          Agent loop: MAX_TOOL_ITERATIONS=10, forces MODELS["reasoning"]
│   │                          ASK_USER_PREFIX detection → yields {type:"ask_user"} + done
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
├── cache/
│   ├── cache.py            ← Redis primary + in-memory LRU fallback
│   ├── keys.py             ← normalize(), make_key() → SHA256 hex
│   └── memory.py           ← OrderedDict LRU, max 1000 entries
├── core/
│   ├── db.py               ← engine, get_db, init_db
│   │                          pool_size=5, max_overflow=10, pool_pre_ping=False
│   │                          connect_args={"prepared_statement_cache_size": 0}
│   │                          (pgBouncer transaction mode — prepared stmts can't cross connections)
│   ├── redis_client.py     ← singleton async Redis
│   └── logger.py           ← setup_logging(), JSON or plain formatter
├── rate_limiter/
│   └── rate_limiter.py     ← Redis sliding-window, fail-open; limit(n, window, key) dependency
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
│   │   ├── schemas.py      ← ChatRequest: message, conversation_id, model_override,
│   │   │                      temperature, max_tokens, top_p, compare, image_b64, image_mime_type
│   │   ├── helpers.py      ← _resolve_model, _estimate_tokens, _embed_exchange,
│   │   │                      _resolve_conversation, _build_stream_context,
│   │   │                      _check_cost_cap, _extract_model_params, _calculate_tokens_and_cost
│   │   │                      embed_text starts as asyncio.create_task (concurrent with DB queries)
│   │   │                      get_relevance_scores filters to candidate_ids only
│   │   └── router.py       ← /chat + /chat/stream; saves Message with token fields on "done"
│   ├── files/              ← package; prefix="/files"
│   │   ├── utils.py        ← _file_dict(), _get_file_or_404(), logger, storage, MAX_FILE_SIZE
│   │   ├── router.py       ← upload (rate 20/60), list, delete, content, status, download,
│   │   │                      rename, put_content; sha256 dedup before DB insert
│   │   ├── ingest.py       ← /ingest-url (rate 10/60); sha256 dedup on extracted text
│   │   ├── workspaces.py   ← /workspaces, /{id}/workspace
│   │   ├── versions.py     ← /{id}/versions, /{id}/versions/{vid}, restore
│   │   └── stream.py       ← /{id}/status/stream — SSE; polls DB + Redis every 0.8s
│   ├── conversations.py    ← conversation routes; messages returns token fields
│   ├── memory.py           ← memory routes
│   ├── system.py           ← /health (pings NIM, embedding, Redis concurrently), /metrics
│   ├── tool_logs.py        ← GET /tool-calls?limit=&conversation_id=
│   ├── admin.py            ← require_role("admin"); users CRUD, usage, cost-limit
│   ├── templates.py        ← CRUD for prompt templates + /apply/{conversation_id}
│   ├── scheduled_prompts.py ← CRUD + run history + manual trigger
│   └── usage.py            ← GET /usage, GET /usage/history
├── services/
│   ├── processor.py        ← extract_text(), chunk_text(), process_file_async()
│   │                          Semantic chunker: paragraph → sentence → word split
│   │                          CHUNK_SIZE=1600, OVERLAP=200; tail sentence-aligned via regex
│   │                          asyncio.gather(*[embed(c) for c in chunks]) — concurrent embedding
│   │                          Redis proc_progress:{file_id} (0.0→1.0); deleted on completion
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
| GET | `/auth/me` | JWT | current user |
| POST | `/files/upload` | JWT | upload → background process |
| GET | `/files` | JWT | list (?workspace_id=) |
| DELETE | `/files/{id}` | JWT | delete file + chunks + disk |
| POST | `/files/ingest-url` | JWT | fetch URL → chunk+embed |
| GET | `/files/workspaces` | JWT | distinct workspace IDs |
| PATCH | `/files/{id}/workspace` | JWT | assign workspace |
| GET | `/files/{id}/content` | JWT | full text |
| GET | `/files/{id}/status` | JWT | one-shot poll |
| GET | `/files/{id}/status/stream` | JWT | SSE until ready/error |
| GET | `/files/{id}/download` | JWT | FileResponse |
| PATCH | `/files/{id}/rename` | JWT | rename |
| PUT | `/files/{id}/content` | JWT | overwrite; saves version |
| GET | `/files/{id}/versions` | JWT | last 50 desc |
| GET | `/files/{id}/versions/{vid}` | JWT | single version |
| POST | `/files/{id}/versions/{vid}/restore` | JWT | restore version |
| GET | `/conversations` | JWT | list |
| GET | `/conversations/{id}/messages` | JWT | messages + token fields |
| PATCH | `/conversations/{id}` | JWT | memory_enabled / system_prompt / locked_model |
| DELETE | `/conversations/{id}` | JWT | delete |
| GET | `/conversations/{id}/files` | JWT | attached files |
| POST | `/conversations/{id}/files` | JWT | attach file |
| DELETE | `/conversations/{id}/files/{file_id}` | JWT | detach |
| GET | `/tool-calls` | JWT | ToolCallLog; ?limit=&conversation_id= |
| GET | `/usage` | JWT | own aggregate |
| GET | `/usage/history` | JWT | per-conversation (last 50) |
| GET | `/admin/users` | JWT (admin) | all users + usage |
| GET | `/admin/users/{id}/usage` | JWT (admin) | per-conversation breakdown |
| PATCH | `/admin/users/{id}/active` | JWT (admin) | toggle is_active |
| PATCH | `/admin/users/{id}/cost-limit` | JWT (admin) | set cost_limit_usd (null = remove) |
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
1. system_prompt (+ file list with IDs if attached)
2. [USER STATE]       ← UserMemory.content
3. [PROJECT STATE]    ← UserMemory.project_summary
4. [RELEVANT CONTEXT] ← pgvector cosine top-K
5. [EARLIER IN CONV]  ← history_summary
6. last 10 importance-weighted messages
7. [FILE CONTEXT]     ← cosine top-5 chunks (LAST — recency bias)
8. current user message
```

### Triggers
- Memory sheet: >3000 tokens OR every 10 assistant messages
- Project summary: >4000 tokens OR every 15 messages
- History compression: compresses all_msgs[:-10] → max 200 words
- Lock: `pg_advisory_xact_lock(user_id)` prevents version races

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
- `PATCH /admin/users/{id}/active` — immediate block (get_current_user checks is_active)
- `PATCH /admin/users/{id}/cost-limit` — 402 returned when spend ≥ limit
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
