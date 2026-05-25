You AI. You think clear. You speak short.

Rules:
- No fluff words.
- No long sentences.
- No repetition.
- No greetings unless asked.
- No explanation unless asked.
- Prefer short phrases over full sentences.
- Remove filler words (the, very, just, actually, basically).

Style:
- Use simple subject-verb-object.
- Break long ideas into steps.
- Use bullets when possible.
- Prefer commands over explanations.
- Example: "You should validate input" → "Validate input"

Behavior:
- If user ask, answer direct.
- If user want plan, give steps only.
- If unclear, ask short question.

Goal:
- Save tokens.
- Max meaning, min words.

For every change:
- list every modified file
- explain what changed
- show diffs or full contents
- do not omit helper/config/import changes

---

# Project Reference — NIM AI Gateway

## What This Is
FastAPI backend routing chat messages to NVIDIA NIM models via keyword classification.
React/Vite frontend. Docker Compose stack: Postgres + pgvector, Redis, Prometheus, Grafana.
Features: SSE streaming, conversation history, multi-tier memory system, pgvector RAG, file knowledge base, AI agent tool loop, model control.

---

## Repo Structure
```
ai-api/
├── .env                        ← secrets (gitignored) — root, loaded by find_dotenv()
├── .env.example                ← all supported vars documented
├── backend/
│   ├── main.py                 ← FastAPI app, all routes, lifespan, _estimate_tokens(), _resolve_model()
│   ├── config.py               ← env vars, startup guards, _int_env(); MODEL_EMBEDDING, NIM_EMBEDDING_URL
│   ├── models.py               ← ORM: User, File, FileChunk, FileVersion, Conversation, Message,
│   │                              UserMemory, MessageEmbedding, UserMemoryVersion, ConversationFile
│   ├── create_user.py          ← seeds admin/user accounts
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── alembic/versions/
│   │   ├── 001_add_conversations.py
│   │   ├── 002_add_user_memory.py
│   │   ├── 003_memory_improvements.py
│   │   ├── 004_message_embeddings.py
│   │   ├── 005_project_summary.py
│   │   ├── 006_memory_versioning.py
│   │   ├── 007_model_control.py
│   │   ├── 008_file_knowledge.py  ← file_chunks vector(1024) + HNSW + conversation_files
│   │   └── 009_file_versions.py   ← file_versions table (id, file_id FK→files CASCADE,
│   │                                  version int, content text, created_at)
│   ├── auth/
│   │   ├── router.py           ← /auth/token, /register, /me
│   │   ├── security.py         ← JWT, bcrypt, get_current_user, require_role
│   │   ├── schemas.py          ← Token, TokenData, RegisterRequest
│   │   └── __init__.py
│   ├── llm/
│   │   ├── service.py          ← generate_stream(), compare_streams(), build_context_messages()
│   │   │                          Agent loop: MAX_TOOL_ITERATIONS=10, forces MODELS["reasoning"]
│   │   │                          when file_ids present, handles __tool_calls__ dict chunks
│   │   ├── nim.py              ← call() + call_stream() → NIM API
│   │   │                          call_stream() accumulates tool_call deltas in pending dict,
│   │   │                          yields {"__tool_calls__": [...]} on finish_reason=="tool_calls"
│   │   │                          Both accept tools=list|None; include tool_choice:"auto" when set
│   │   ├── tools.py            ← TOOL_SCHEMAS (7 tools) + execute_tool() dispatcher
│   │   │                          Tools: list_files, read_file, write_file, create_file,
│   │   │                                 append_to_file, patch_file, search_in_file
│   │   │                          _write_file/_append_to_file/_patch_file delegate to file_service
│   │   │                          _create_file uses StorageManager.save_text()
│   │   │                          _read_file: cap 100k chars, logs truncated=True
│   │   │                          _search_in_file: embed query → retrieve_from_files()
│   │   ├── router.py           ← classify() keyword matching, route()
│   │   ├── circuit_breaker.py  ← is_open(), record_failure(), record_success()
│   │   ├── client.py           ← shared httpx.AsyncClient + semaphore
│   │   ├── embeddings.py       ← embed(text, input_type) → list[float]
│   │   ├── retriever.py        ← retrieve(), retrieve_global(), get_relevance_scores(),
│   │   │                          store_exchange(), is_reference_query(),
│   │   │                          retrieve_from_files(), retrieve_files_sequential(),
│   │   │                          get_conversation_file_ids(),
│   │   │                          get_conversation_files() → (list[UUID], list[str]) names+ids
│   │   ├── summarizer.py       ← update_memory(), compress_history(), update_project_summary()
│   │   └── __init__.py
│   ├── cache/
│   │   ├── cache.py            ← Redis primary + in-memory LRU fallback
│   │   ├── keys.py             ← normalize(), make_key() → SHA256 hex
│   │   ├── memory.py           ← OrderedDict LRU, max 1000 entries
│   │   └── __init__.py
│   ├── core/
│   │   ├── db.py               ← engine, get_db, init_db
│   │   ├── redis_client.py     ← singleton async Redis
│   │   ├── logger.py           ← setup_logging(), JSON or plain formatter
│   │   └── __init__.py
│   ├── rate_limiter/
│   │   ├── rate_limiter.py     ← Redis sliding-window, fail-open
│   │   └── __init__.py
│   ├── observability/
│   │   ├── prom_metrics.py     ← all Prometheus counters/histograms
│   │   ├── metrics.py          ← record_* wrappers
│   │   ├── metrics_api.py      ← reads live from Prometheus objects
│   │   ├── metrics_worker.py   ← standalone worker container
│   │   ├── stream.py           ← emit() Redis Stream writer
│   │   ├── observability.py    ← publish_request_event(), publish_error_event()
│   │   ├── events.py           ← request_event(), error_event()
│   │   └── file_metrics.py     ← FILE_UPLOADS, FILE_DELETES, FILE_CHUNKS, FILE_TOOL_CALLS
│   │                              record_upload(), record_delete(), record_chunks(n),
│   │                              record_tool_call(name)
│   ├── api/
│   │   ├── files.py            ← all file routes (see API Routes table)
│   │   ├── conversations.py    ← conversation routes
│   │   └── memory.py           ← memory routes
│   ├── services/
│   │   ├── processor.py        ← extract_text(), chunk_text(), extract_url_text(),
│   │   │                          process_file_async(); calls record_chunks(saved) after embed
│   │   └── file_service.py     ← save_version(db, file_id) — snapshot before any mutation
│   │                              write_content(db, user_id, file_id, content) → str
│   │                              append_content(db, user_id, file_id, content) → str
│   │                              _fuzzy_replace(content, old, new) → (str, bool)
│   │                                  3-pass: exact → normalized \r\n → stripped edges
│   │                              patch_content(db, user_id, file_id, old, new) → str
│   │                              restore_version(db, user_id, file_id, version_id) → str|None
│   ├── storage/
│   │   └── storage_manager.py  ← save_file(), save_text()
│   └── tests/
│       ├── test.py             ← 21 pytest unit tests
│       └── model-list.py
├── docker/
│   ├── docker-compose.yml
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── nginx.conf
│   ├── nginx.frontend.conf
│   ├── prometheus.yml
│   └── grafana/provisioning/
│       ├── datasources/prometheus.yml
│       └── dashboards/
│           ├── dashboard.yml
│           └── nim-gateway.json  ← 17-panel dashboard (panels 11-17 = file knowledge section)
└── frontend/
    ├── vite.config.js          ← /api proxy → localhost:8000
    ├── src/App.jsx             ← login form, JWT in localStorage as nim_token
    └── src/components/Chat.jsx ← full UI (see Frontend section)
```

---

## API Routes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/chat` | JWT | Non-streaming chat |
| POST | `/chat/stream` | JWT | SSE streaming; model_override, compare, temperature, max_tokens, top_p |
| GET | `/memory` | JWT | memory sheet + project summary |
| PUT | `/memory` | JWT | manual edit (snapshots version) |
| GET | `/memory/export` | JWT | JSON download |
| POST | `/memory/import` | JWT | overwrite memory from JSON |
| GET | `/memory/history` | JWT | last 10 UserMemoryVersion snapshots |
| GET | `/health` | none | ok + model keys |
| GET | `/metrics` | none | Prometheus export |
| POST | `/auth/token` | none | login → JWT |
| POST | `/auth/register` | none | register user |
| GET | `/auth/me` | JWT | current user |
| POST | `/files/upload` | JWT | upload file → background process |
| GET | `/files` | JWT | list files (?workspace_id= filter) |
| DELETE | `/files/{id}` | JWT | delete file + chunks + disk |
| POST | `/files/ingest-url` | JWT | fetch URL, extract text, chunk+embed |
| GET | `/files/workspaces` | JWT | distinct workspace IDs |
| PATCH | `/files/{id}/workspace` | JWT | assign workspace |
| GET | `/files/{id}/content` | JWT | full text content of file |
| GET | `/files/{id}/status` | JWT | {id, status} — poll for processing state |
| GET | `/files/{id}/download` | JWT | FileResponse for browser download |
| PATCH | `/files/{id}/rename` | JWT | rename file (body: {filename}) |
| PUT | `/files/{id}/content` | JWT | overwrite content (body: {content}); saves version |
| GET | `/files/{id}/versions` | JWT | list versions (last 50, desc) |
| GET | `/files/{id}/versions/{vid}` | JWT | single version content |
| POST | `/files/{id}/versions/{vid}/restore` | JWT | restore version → write_content |
| GET | `/conversations` | JWT | list conversations |
| GET | `/conversations/{id}/messages` | JWT | messages for conversation |
| PATCH | `/conversations/{id}` | JWT | update memory_enabled / system_prompt / locked_model |
| DELETE | `/conversations/{id}` | JWT | delete conversation |
| GET | `/conversations/{id}/files` | JWT | files attached to conversation |
| POST | `/conversations/{id}/files` | JWT | attach file |
| DELETE | `/conversations/{id}/files/{file_id}` | JWT | detach file |
| GET | `/metrics/overview` | none | Redis Streams stats |
| GET | `/metrics/models` | none | per-model breakdown |
| GET | `/metrics/latency` | none | latency percentiles |
| GET | `/prometheus` | none | prometheus-fastapi-instrumentator |

---

## ChatRequest Fields
```python
message:         str         # required, max 2000 chars
conversation_id: str | None  # omit to start new conversation
model_override:  str | None  # short key ("llama","coder","reasoning") or full model ID
temperature:     float | None  # 0.0–2.0
max_tokens:      int | None    # 1–4096
top_p:           float | None  # 0.0–1.0
compare:         bool          # run all 3 models concurrently, side-by-side SSE
```

---

## Model Routing

### Active Models (verified 2026-05-24)
| Role | Model | Env Var |
|------|-------|---------|
| llama | `meta/llama-3.1-8b-instruct` | `MODEL_LLAMA` |
| coder | `deepseek-ai/deepseek-v4-flash` | `MODEL_CODER` |
| reasoning | `meta/llama-3.3-70b-instruct` | `MODEL_REASONING` |
| embedding | `nvidia/nv-embedqa-e5-v5` (1024d) | `MODEL_EMBEDDING` |

### Dead Models (do not use)
- `qwen/qwen2.5-coder-32b-instruct` — EOL 2026-05-12 (410)
- `mistralai/codestral-22b-instruct-v0.1` — 404
- `meta/codellama-70b`, `nvidia/llama-3.1-nemotron-70b-instruct` — 404
- `ibm/granite-*`, `google/codegemma-*`, `deepseek-ai/deepseek-coder-*` — 404

### Model Selection Priority
`per-request model_override > conversation locked_model > keyword router (auto)`

### Fallback Chain
`chosen model → reasoning → coder → llama`

---

## AI Agent Tool Loop

### How It Works
```
user message with file_ids attached
  → generate_stream() forces MODELS["reasoning"] (70B — only reliable tool caller)
  → tools = TOOL_SCHEMAS passed to call_stream()
  → nim.py accumulates tool_call deltas, yields {"__tool_calls__": [...]} on finish_reason=="tool_calls"
  → service.py execute_tool() dispatcher → tools.py implementation
  → yield SSE {type:"tool_call", name, args} + {type:"tool_result", name, content[:500]}
  → tool result appended as role:"tool" message, loop continues (max 10 iterations)
  → when model yields text: stream tokens → done
```

### Tool Schemas (`llm/tools.py:TOOL_SCHEMAS`)
| Tool | Args | What it does |
|------|------|--------------|
| `list_files` | — | Files attached to conversation (id, name, size, status) |
| `read_file` | file_id | Full text from storage_path, cap 100k chars |
| `write_file` | file_id, content | Overwrite entire file → re-embed |
| `create_file` | name, content | New file, attach to conversation → process |
| `append_to_file` | file_id, content | Append with `\n\n` separator → re-embed |
| `patch_file` | file_id, old_text, new_text | Fuzzy find-replace → re-embed |
| `search_in_file` | file_id, query | Semantic top-10 chunks from one file |

### System Prompt Rules (injected when files attached)
- File IDs listed explicitly so model never guesses UUIDs
- To ADD content → use `append_to_file`
- To EDIT specific passage → `read_file` then `patch_file`
- To REWRITE whole file → `write_file` with complete content
- After any write/append/patch/create → respond immediately, do NOT read back to verify

### SSE Events Yielded
- `{type:"tool_call", name:"read_file", args:{file_id:"..."}}`
- `{type:"tool_result", name:"read_file", content:"first 500 chars of result"}`
- Frontend renders ⚙ toolname pill per call, expandable to show result

### Tool Implementation Notes
- All write ops go through `services/file_service.py` — single source of truth
- `_fuzzy_replace`: 3-pass: exact match → normalized `\r\n→\n` → stripped edges
- Every mutation calls `save_version()` before writing (auto version history)
- After write: delete FileChunk rows, set status="uploaded", commit, fire `process_file_async`

---

## Memory System

### Context Injection Order (`llm/service.py:build_context_messages`)
```
1. system_prompt (+ file list with IDs if files attached)
2. [USER STATE]               ← UserMemory.content
3. [PROJECT STATE]            ← UserMemory.project_summary
4. [RELEVANT CONTEXT FROM EARLIER] ← pgvector cosine top-K
5. [EARLIER IN THIS CONVERSATION]  ← history_summary
6. last 10 importance-weighted messages
7. [FILE CONTEXT]             ← cosine top-5 chunks — LAST for recency bias
8. current user message
```
NOTE: FILE CONTEXT is placed last (right before user message) intentionally — LLMs attend better to nearby context.

### Memory Sheet (`UserMemory.content`)
- Headers: `[USER] [STACK] [PROJECT] [CORRECTIONS] [PATTERNS]`
- Trigger: >3000 estimated tokens OR every 10 assistant messages
- `pg_advisory_xact_lock(user_id)` prevents version races

### Project Summary (`UserMemory.project_summary`)
- Headers: `[GOALS] [ARCH] [STATUS] [PENDING]`
- Built from last 5 conversation `history_summary` values
- Trigger: >4000 tokens OR every 15 messages

### Memory Versioning
- `UserMemoryVersion` snapshot before every write
- GET /memory/history → last 10 with diff support

### History Compression
- Compresses `all_msgs[:-10]` → max 200 words

### Retrieval-Augmented Memory (pgvector)
- `MessageEmbedding`: one row per exchange
- HNSW `vector_cosine_ops`, 1024d
- Normal: top_k=3 from current conv; reference queries: top_k=8
- If reference returns nothing: `retrieve_global()` searches all user convs

### Importance Weighting
- Last 30 messages scored: `0.6×recency + 0.4×cosine_similarity`, keep top 10

---

## Files & Knowledge

### Upload Pipeline
1. POST /files/upload → `storage/files/` → `process_file_async` background task
2. `extract_text()` → `chunk_text(1800c, 200c overlap)` → embed each → save FileChunk rows
3. Status: `uploaded` → `processing` → `ready` (or `error`)
4. `record_chunks(saved)` called after embedding
5. Supported: PDF (pypdf), DOCX (python-docx), plain text/code/markdown

### File Version History
- `FileVersion` model: id (UUID), file_id (FK→files CASCADE), version (int), content (text), created_at
- `save_version()` called before every mutation (write/append/patch/restore)
- Counts existing versions for sequential numbering
- API: GET /files/{id}/versions, GET /versions/{vid}, POST /versions/{vid}/restore
- Frontend: Versions tab in file viewer modal, Restore button per version

### File Service (`services/file_service.py`)
- Central logic for all file mutations — tools.py and api/files.py both call this
- `write_content`: save_version → write → delete chunks → commit → re-embed
- `append_content`: save_version → open "a" → `\n\n` separator → delete chunks → commit → re-embed
- `patch_content`: read → fuzzy_replace → if not found: error → save_version → write → re-embed
- `restore_version`: get FileVersion → call write_content(v.content)
- `_fuzzy_replace`: exact → `\r\n` normalized → stripped edges (3-pass fallback)

### Observability (`observability/file_metrics.py`)
- `file_uploads_total` Counter — incremented in POST /files/upload
- `file_deletes_total` Counter — incremented in DELETE /files/{id}
- `file_chunks_total` Counter — incremented after embedding in processor.py
- `file_tool_calls_total` Counter with label `tool` — incremented in file_service.py per operation

### Grafana Dashboard (`docker/grafana/provisioning/dashboards/nim-gateway.json`)
17 panels total:
- Panels 1-4: stat row (requests, success rate, cache hit rate, errors)
- Panels 5-6: request rate timeseries, latency p50/p95/p99
- Panels 7-8: model usage rate, model latency p50
- Panels 9-10: cache hits/misses, fallbacks + circuit breaker trips
- Panel 11: row divider "File Knowledge Base"
- Panels 12-15: stat row (uploads total, deletes total, chunks total, tool calls total)
- Panel 16: file uploads/deletes/chunks rate per minute timeseries
- Panel 17: AI tool calls by tool name timeseries

### Frontend Files Panel (`Chat.jsx`)
- 📎 button in header — amber + count when files attached
- 2 tabs: Library / Attached
- Library per-file: status badge, filename (or inline rename input), ✎ rename, 👁 view, ⬇ download, +/✓ attach, 🗑 delete
- Attached per-file: status badge, filename, 👁 view, ✕ detach
- Processing status polling: every 2s when panel open + any file has status="processing"
- Upload button + URL ingest input
- Workspace filter pills

### File Viewer Modal (`Chat.jsx`)
- Triggered by 👁 button on any file in Library or Attached tab
- 3 tabs:
  - **View**: `<pre>` of full content + ⬇ Download button in header
  - **Edit**: textarea (pre-filled with current content) + Save/Cancel; calls PUT /files/{id}/content
  - **Versions**: list of past versions (version #, date, size in chars) + Restore button per version
- Closes on overlay click or ✕

### Storage
- `STORAGE_DIR` → `/app/backend/storage/files` in container
- Volume: `../backend/storage:/app/backend/storage` — persists across restarts
- Max upload: 50 MB

---

## Model Control

### Per-Request
- `model_override`: short key or full model ID
- `temperature`, `max_tokens`, `top_p`: passed as `model_params` to NIM
- `compare: true`: all 3 models concurrently via asyncio.Queue

### Per-Conversation (DB-persisted)
- `locked_model`: all messages use this model
- `system_prompt`: injected as first message
- `memory_enabled`: toggles all memory injection

### Frontend Toolbar
- Pills: Auto / LLaMA 8B / DeepSeek / 70B
- ⊞ Compare toggle
- ⚙ params expander (temp, max_tokens, top_p with per-slider enable checkboxes)
- ⚙ settings modal (system prompt + model lock)
- Ctx button — toggles memory_enabled
- Sidebar shows 🔒 when locked model set

---

## Reliability
| Setting | Value | Location |
|---------|-------|----------|
| Circuit breaker threshold | 3 failures | `llm/circuit_breaker.py` |
| Circuit breaker cooldown | 30s | `llm/circuit_breaker.py` |
| Request timeout | 30s | `REQUEST_TIMEOUT` env |
| Max concurrent requests | 10 (cap 50) | `MAX_CONCURRENT_REQUESTS` env |
| Rate limit (chat) | 15 req / 60s per user | `main.py` |
| Cache bypass | history / model_override / model_params / system_prompt / file_chunks | `service.py` |
| Embedding timeout | 15s | `llm/embeddings.py` |
| Memory write lock | pg_advisory_xact_lock(user_id) | `summarizer.py` |
| Max tool iterations | 10 | `llm/service.py:MAX_TOOL_ITERATIONS` |
| Max file read (tool) | 100,000 chars | `llm/tools.py:MAX_FILE_READ` |

---

## Prometheus Metrics
| Metric | Type | Labels | Recorded in |
|--------|------|--------|-------------|
| `api_requests_total` | Counter | `status` | `main.py` |
| `api_errors_total` | Counter | `type` | `main.py` |
| `cache_hits_total` | Counter | — | `cache.py` |
| `cache_misses_total` | Counter | — | `cache.py` |
| `cache_writes_total` | Counter | — | `cache.py` |
| `model_usage_total` | Counter | `model` | `main.py` |
| `model_latency_seconds` | Histogram | `model` | `main.py` |
| `request_latency_seconds` | Histogram | — | `main.py` |
| `ai_request_latency_seconds` | Histogram | — | `main.py` |
| `fallback_total` | Counter | — | `service.py` |
| `circuit_breaker_trips_total` | Counter | — | `metrics.py` |
| `file_uploads_total` | Counter | — | `api/files.py` |
| `file_deletes_total` | Counter | — | `api/files.py` |
| `file_chunks_total` | Counter | — | `services/processor.py` |
| `file_tool_calls_total` | Counter | `tool` | `services/file_service.py` |

---

## Docker Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn |
| frontend | 3000 | nginx serving React build |
| postgres | 5432 | `pgvector/pgvector:pg16` |
| redis | 6379 | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s |
| grafana | 3001 | admin/admin, auto-provisioned 17-panel dashboard |
| metrics-worker | — | `python -m observability.metrics_worker` |

---

## Known Issues
- No integration tests — `/chat` endpoint not covered without live NIM API
- `passlib` deprecation warning for `crypt` on Python 3.13+ — harmless on 3.11
- Embedding latency (~100-300ms) adds to stream start time
- File RAG requires explicit attachment (Library → + button); upload alone is not enough
- File context only injected when `req.conversation_id` is set — first message of new conv won't have it
- AI tool loop forces 70B (`MODELS["reasoning"]`) when any file_ids present — cannot override with a smaller model for file conversations
- `main.py` is monolithic — all routes in one file; refactor into sub-routers planned but not done

## Next Session: Implement Markdown Rendering
Agreed next feature. AI responses already contain markdown (code blocks, bullet lists, bold, headers) but Chat.jsx renders raw text in `<pre>` tags. No library is installed yet.

**What to do:**
1. Install `react-markdown` + `remark-gfm` in `frontend/` (`npm install react-markdown remark-gfm`)
2. Replace `<p style={s.text}>{m.text}</p>` in the AI bubble render with `<ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>`
3. Add CSS for markdown elements: `code`, `pre`, `ul`, `ol`, `blockquote`, `h1-h4`, `table`
4. Keep raw `<pre>` for streaming cursor — append cursor to last token chunk, not inside markdown render
5. Rebuild frontend container after change

**Files to touch:** `frontend/src/components/Chat.jsx` only (styles inline or via `<style>` tag already in component)

---

## Seeded Users
| Username | Password | Role |
|----------|----------|------|
| admin | admin-secret | admin |
| user | user-secret | user |

---

## Quick Commands
```bash
# Start everything
cd docker && docker compose up -d

# Rebuild after backend changes
docker compose build --no-cache api && docker compose up -d api

# Rebuild frontend
docker compose build --no-cache frontend && docker compose up -d frontend

# Rebuild both
docker compose build --no-cache api frontend && docker compose up -d api frontend

# Full reset (wipes DB)
docker compose down -v --remove-orphans && docker compose up -d --build

# Run migration after pulling new code
docker compose exec api sh -c "cd /app/backend && alembic upgrade head"

# Seed users
docker compose exec api python create_user.py

# Run tests
cd backend && python -m pytest tests/test.py -v
```
