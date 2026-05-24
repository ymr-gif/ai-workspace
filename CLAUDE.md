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
Features: SSE streaming, conversation history, multi-tier memory system, pgvector RAG, file knowledge base, model control.

---

## Repo Structure
```
ai-api/
├── .env                        ← secrets (gitignored) — root, loaded by find_dotenv()
├── .env.example                ← all supported vars documented
├── backend/
│   ├── main.py                 ← FastAPI app, all routes, lifespan, _estimate_tokens(), _resolve_model()
│   ├── config.py               ← env vars, startup guards, _int_env(); MODEL_EMBEDDING, NIM_EMBEDDING_URL
│   ├── models.py               ← ORM: User, File, FileChunk, Conversation, Message, UserMemory,
│   │                              MessageEmbedding, UserMemoryVersion, ConversationFile
│   ├── create_user.py          ← seeds admin/user accounts
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── alembic/versions/
│   │   ├── 001_add_conversations.py      ← conversations + messages
│   │   ├── 002_add_user_memory.py        ← user_memory table
│   │   ├── 003_memory_improvements.py   ← history_summary + last_summarized_at
│   │   ├── 004_message_embeddings.py    ← message_embeddings + HNSW index
│   │   ├── 005_project_summary.py       ← project_summary column on user_memory
│   │   ├── 006_memory_versioning.py     ← memory_enabled on conversations + user_memory_versions table
│   │   ├── 007_model_control.py         ← system_prompt + locked_model on conversations
│   │   └── 008_file_knowledge.py        ← file_chunks vector(1024) + HNSW + conversation_files table
│   ├── auth/
│   │   ├── router.py           ← /auth/token, /register, /me
│   │   ├── security.py         ← JWT, bcrypt, get_current_user, require_role
│   │   ├── schemas.py          ← Token, TokenData, RegisterRequest
│   │   └── __init__.py         ← re-exports: auth_router, get_current_user, require_role
│   ├── llm/
│   │   ├── service.py          ← generate_stream(), compare_streams(), build_context_messages()
│   │   ├── nim.py              ← call() + call_stream() → NIM API; model_params passthrough
│   │   ├── router.py           ← classify() keyword matching, route()
│   │   ├── circuit_breaker.py  ← is_open(), record_failure(), record_success()
│   │   ├── client.py           ← shared httpx.AsyncClient + semaphore
│   │   ├── embeddings.py       ← embed(text, input_type) → list[float] via NIM embeddings API
│   │   ├── retriever.py        ← retrieve(), retrieve_global(), get_relevance_scores(),
│   │   │                          store_exchange(), is_reference_query(),
│   │   │                          retrieve_from_files(), retrieve_files_sequential(),
│   │   │                          get_conversation_file_ids()
│   │   ├── summarizer.py       ← update_memory(), compress_history(), update_project_summary()
│   │   │                          advisory lock on user_id to prevent version race
│   │   └── __init__.py
│   ├── cache/
│   │   ├── cache.py            ← Redis primary + in-memory LRU fallback
│   │   ├── keys.py             ← normalize(), make_key() → SHA256 hex
│   │   ├── memory.py           ← OrderedDict LRU, max 1000 entries
│   │   └── __init__.py         ← re-exports: get_cached_response, set_cached_response
│   ├── core/
│   │   ├── db.py               ← engine, get_db, init_db (CREATE EXTENSION vector + checkfirst)
│   │   ├── redis_client.py     ← singleton async Redis, init_redis(), get_redis()
│   │   ├── logger.py           ← setup_logging(), JSON or plain formatter
│   │   └── __init__.py
│   ├── rate_limiter/
│   │   ├── rate_limiter.py     ← Redis sliding-window, fail-open
│   │   └── __init__.py         ← re-exports: limit
│   ├── observability/
│   │   ├── prom_metrics.py     ← all Prometheus counters/histograms
│   │   ├── metrics.py          ← record_* wrappers
│   │   ├── metrics_api.py      ← reads live from Prometheus objects
│   │   ├── metrics_worker.py   ← standalone worker (own container)
│   │   ├── stream.py           ← emit() Redis Stream writer
│   │   ├── observability.py    ← publish_request_event(), publish_error_event()
│   │   └── events.py           ← request_event(), error_event()
│   ├── api/
│   │   ├── files.py            ← /files/upload, GET /files, DELETE /files/{id},
│   │   │                          POST /files/ingest-url, GET /files/workspaces,
│   │   │                          PATCH /files/{id}/workspace
│   │   ├── conversations.py    ← GET/DELETE /conversations, GET /conversations/{id}/messages,
│   │   │                          PATCH /conversations/{id} (memory_enabled, system_prompt, locked_model),
│   │   │                          GET/POST/DELETE /conversations/{id}/files
│   │   └── memory.py           ← GET/PUT /memory, GET /memory/export, POST /memory/import,
│   │                              GET /memory/history
│   ├── services/
│   │   └── processor.py        ← extract_text() PDF/DOCX/plain, chunk_text() 1800c/200c overlap,
│   │                              extract_url_text() httpx+BeautifulSoup, process_file_async()
│   ├── storage/
│   │   └── storage_manager.py  ← save_file(), save_text(); volume: ../backend/storage
│   └── tests/
│       ├── test.py             ← 21 pytest unit tests
│       └── model-list.py
├── docker/
│   ├── docker-compose.yml      ← postgres: pgvector/pgvector:pg16; storage volume mounted
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── nginx.conf
│   ├── nginx.frontend.conf
│   ├── prometheus.yml
│   └── grafana/provisioning/   ← auto-loaded datasource + 10-panel dashboard
└── frontend/
    ├── vite.config.js          ← /api proxy → localhost:8000
    ├── src/App.jsx             ← login form, JWT in localStorage as nim_token
    └── src/components/Chat.jsx ← sidebar + streaming chat + memory panel + files panel +
                                   model toolbar + compare mode + settings modal
```

---

## API Routes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/chat` | JWT | Non-streaming chat |
| POST | `/chat/stream` | JWT | SSE streaming; supports model_override, compare, temperature, max_tokens, top_p |
| GET | `/memory` | JWT | Returns memory sheet + project summary |
| PUT | `/memory` | JWT | Manual memory edit (snapshots version) |
| GET | `/memory/export` | JWT | JSON download with Content-Disposition |
| POST | `/memory/import` | JWT | Overwrite memory from JSON |
| GET | `/memory/history` | JWT | Last 10 UserMemoryVersion snapshots |
| GET | `/health` | none | ok + model keys |
| GET | `/metrics` | none | Prometheus export |
| POST | `/auth/token` | none | Login → JWT |
| POST | `/auth/register` | none | Register user |
| GET | `/auth/me` | JWT | Current user |
| POST | `/files/upload` | JWT | Upload file, triggers background processing |
| GET | `/files` | JWT | List files (optional ?workspace_id= filter) |
| DELETE | `/files/{id}` | JWT | Delete file + chunks + disk |
| POST | `/files/ingest-url` | JWT | Fetch URL, extract text, chunk + embed |
| GET | `/files/workspaces` | JWT | Distinct workspace IDs for this user |
| PATCH | `/files/{id}/workspace` | JWT | Assign file to workspace |
| GET | `/conversations` | JWT | List conversations (includes memory_enabled, system_prompt, locked_model) |
| GET | `/conversations/{id}/messages` | JWT | Messages for conversation |
| PATCH | `/conversations/{id}` | JWT | Update memory_enabled / system_prompt / locked_model |
| DELETE | `/conversations/{id}` | JWT | Delete conversation |
| GET | `/conversations/{id}/files` | JWT | Files attached to conversation |
| POST | `/conversations/{id}/files` | JWT | Attach file to conversation |
| DELETE | `/conversations/{id}/files/{file_id}` | JWT | Detach file |
| GET | `/metrics/overview` | none | Redis Streams stats |
| GET | `/metrics/models` | none | Per-model breakdown |
| GET | `/metrics/latency` | none | Latency percentiles |
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

## Memory System (full stack)

### Context Injection Order (`llm/service.py:build_context_messages`)
```
1. system_prompt              ← Conversation.system_prompt (if set)
2. [USER STATE]               ← UserMemory.content (500w max, key:value)
3. [PROJECT STATE]            ← UserMemory.project_summary (300w max, key:value)
4. [FILE CONTEXT]             ← top-5 cosine chunks from attached files (or sequential fallback)
5. [RELEVANT CONTEXT FROM EARLIER] ← top-K pgvector cosine results (MessageEmbedding)
6. [EARLIER IN THIS CONVERSATION]  ← Conversation.history_summary (200w max)
7. last 10 importance-weighted msgs ← scored 0.6×recency + 0.4×relevance
8. current user message
```

### Memory Sheet (`UserMemory.content`)
- Headers: `[USER] [STACK] [PROJECT] [CORRECTIONS] [PATTERNS]`
- Trigger: context >3000 estimated tokens OR every 10 assistant messages
- Background: `asyncio.create_task(update_memory(user_id, conv_id))`
- Reads all messages since `last_summarized_at`
- pg_advisory_xact_lock(user_id) prevents version races with project summary

### Project Summary (`UserMemory.project_summary`)
- Headers: `[GOALS] [ARCH] [STATUS] [PENDING]`
- Built from last 5 conversation `history_summary` values
- Trigger: context >4000 estimated tokens OR every 15 total messages
- Background: `asyncio.create_task(update_project_summary(user_id))`
- Same advisory lock as memory sheet

### Memory Versioning (`UserMemoryVersion`)
- Snapshot saved before every write (manual or auto)
- GET /memory/history returns last 10 versions with diff support in frontend

### History Compression (`Conversation.history_summary`)
- Compresses `all_msgs[:-10]` → max 200 words
- Same trigger as project summary

### Retrieval-Augmented Memory (pgvector)
- `MessageEmbedding` table: one row per exchange (user+assistant pair)
- Embedding: `nvidia/nv-embedqa-e5-v5`, 1024d, `input_type=passage` for store / `query` for search
- Index: HNSW with `vector_cosine_ops` — O(log n) ANN search
- Normal queries: top_k=3 from current conversation
- Reference queries ("earlier", "remember", "you said"…): top_k=8
- If reference query returns nothing: `retrieve_global()` searches across ALL user conversations

### Importance Weighting
- Loads last 30 messages, scores each: `0.6 × recency + 0.4 × cosine_similarity`
- Keeps top 10, re-sorted chronologically

### Context-Pressure Trigger
- `_estimate_tokens(*texts)` = `sum(len(t) // 4)`
- compress + project: fires at >4000t OR fallback every 15 exchanges
- update_memory: fires at >3000t OR fallback every 10 assistant messages

### Frontend Memory Panel (`Chat.jsx`)
- "Memory" button in header — pulsing green dot while background tasks running
- Slides in from right, overlay closes on click
- 3 tabs: View / Edit / History
- View: sections color-coded USER/STACK/PROJECT/CORRECTIONS/PATTERNS + GOALS/ARCH/STATUS/PENDING
- Edit: textarea for content + project_summary, Save/Cancel
- History: last 10 versions, click to diff against current (set-based line diff)
- Export button → memory.json download; Import button → JSON file picker
- Footer toggle: enable/disable memory for current conversation
- Real-time polling: 2s × 15 after each response, 20s baseline while open
- Content-diff detection — green flash animation on change

---

## Model Control

### Per-Request
- `model_override`: short key or full model ID — bypasses router for that message only
- `temperature`, `max_tokens`, `top_p`: passed as `model_params` to NIM API
- `compare: true`: runs all 3 models concurrently via asyncio.Queue, yields tagged SSE tokens

### Per-Conversation (persisted in DB)
- `locked_model`: all messages use this model (short key resolved to full ID on PATCH)
- `system_prompt`: injected as first system message before all context
- `memory_enabled`: toggles all memory injection for this conversation

### Frontend Model Toolbar (`Chat.jsx`)
- Pills: Auto / LLaMA 8B / DeepSeek / 70B — sends short key as model_override
- ⊞ Compare toggle — side-by-side 3-column response cards
- ⚙ params expander — per-slider enable checkboxes; disabled sliders send null (not included in body)
- ⚙ settings modal — system prompt textarea + model lock pills; saved via PATCH /conversations/{id}
- Ctx button in header — toggles memory_enabled for current conversation
- Lock icon in sidebar + header shows when conversation has locked model

---

## Files & Knowledge

### Upload Pipeline
1. POST /files/upload (multipart) → saves to `storage/files/` → triggers `process_file_async` as background task
2. processor: extract_text() → chunk_text(1800c, 200c overlap) → embed each chunk → save FileChunk rows
3. File status: `uploaded` → `processing` → `ready` (or `error`)
4. Supported: PDF (pypdf), DOCX (python-docx), plain text / code / markdown

### URL Ingestion
- POST /files/ingest-url `{"url": "https://..."}`
- httpx fetch + BeautifulSoup lxml extraction, strips nav/footer/script
- Saved as .txt file, same chunk+embed pipeline

### Workspace Management
- Files can have optional `workspace_id` string tag
- GET /files?workspace_id=X filters by workspace
- GET /files/workspaces returns distinct workspace IDs
- PATCH /files/{id}/workspace to reassign

### Conversation Attachment
- POST /conversations/{id}/files `{"file_id": "..."}` → ConversationFile row
- DELETE /conversations/{id}/files/{file_id} → detach
- Chips above input bar show attached files with ✕ to detach

### File RAG in Chat
- On each message, loads file_ids via get_conversation_file_ids()
- If query_emb available: cosine similarity top-5 via retrieve_from_files()
- If query_emb unavailable (embedding API down): sequential fallback top-10 via retrieve_files_sequential()
- Injected as [FILE CONTEXT] in prompt — always present when files attached
- Cache bypassed when files are attached (use_cache checks file_chunks)

### Storage
- `STORAGE_DIR = "storage/files"` → `/app/backend/storage/files` in container
- Volume: `../backend/storage:/app/backend/storage` — persists across restarts
- Max upload: 50 MB

### Frontend Files Panel (`Chat.jsx`)
- 📎 Files button in header — amber + count when files attached
- Slides in from right
- 2 tabs: Library (all user files) / Attached (files on current conversation)
- Upload button → file picker; URL ingest input → ⬇ Fetch
- Workspace filter pills
- Library: attach/detach button per file, delete button, status badge
- Attached: detach button per file

---

## Reliability
| Setting | Value | Config |
|---------|-------|--------|
| Circuit breaker threshold | 3 failures | `llm/circuit_breaker.py` |
| Circuit breaker cooldown | 30s | `llm/circuit_breaker.py` |
| Request timeout | 30s | `REQUEST_TIMEOUT` in `.env` |
| Max concurrent requests | 10 (cap 50) | `MAX_CONCURRENT_REQUESTS` in `.env` |
| Rate limit (chat) | 15 req / 60s per user | `main.py` |
| Cache | Redis primary + LRU fallback | `cache/cache.py` |
| Cache bypass | when history / model_override / model_params / system_prompt / file_chunks present | `service.py` |
| Embedding timeout | 15s | `llm/embeddings.py` |
| Memory write lock | pg_advisory_xact_lock(user_id) | `summarizer.py` |

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

---

## Docker Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn |
| frontend | 3000 | nginx serving React build |
| postgres | 5432 | `pgvector/pgvector:pg16` image |
| redis | 6379 | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s |
| grafana | 3001 | admin/admin, auto-provisioned dashboard |
| metrics-worker | — | `python -m observability.metrics_worker` |

---

## Known Issues / Pending
- No integration tests — `/chat` endpoint not covered without running NIM API
- `passlib` deprecation warning for `crypt` on Python 3.13+ — harmless on 3.11
- Embedding latency (~100-300ms) adds to request setup time before stream starts
- File RAG only works if file is explicitly ATTACHED to the conversation (Library tab → + button)
  Upload alone is not enough — attachment creates the ConversationFile row that links file to conv
- File context only injected when req.conversation_id is set (not on first message of new conv)
  Attach files to an existing conversation, not before sending the first message

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

# Rebuild after code changes (api only)
docker compose up -d --build api

# Rebuild api + frontend
docker compose up -d --build api frontend

# Full reset (wipes DB)
docker compose down -v --remove-orphans && docker compose up -d --build

# Migrations (run after pulling new code)
docker compose exec api sh -c "cd /app/backend && alembic upgrade head"

# Seed users
docker compose exec api python create_user.py

# Run tests
cd backend && python -m pytest tests/test.py -v
```
