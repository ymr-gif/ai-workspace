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
Features: SSE streaming, conversation history, multi-tier memory system, pgvector RAG, file knowledge base, AI agent tool loop, model control, markdown rendering.

---

## Repo Structure
```
ai-api/
├── .env                        ← secrets (gitignored) — root, loaded by find_dotenv()
├── .env.example                ← all supported vars documented
├── backend/
│   ├── main.py                 ← thin app factory: lifespan, middleware, router includes (~83 lines)
│   ├── config.py               ← env vars, startup guards, _int_env(); MODEL_EMBEDDING, NIM_EMBEDDING_URL
│   ├── models.py               ← ORM: User, File, FileChunk, FileVersion, Conversation, Message,
│   │                              UserMemory, MessageEmbedding, UserMemoryVersion, ConversationFile,
│   │                              ToolCallLog
│   │                              Message has: prompt_tokens, completion_tokens, total_tokens, cost_usd
│   │                              User has: is_active (checked in get_current_user — blocks immediately)
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
│   │   ├── 009_file_versions.py   ← file_versions table
│   │   ├── 010_tool_call_log.py   ← tool_call_logs table (id, user_id, conversation_id,
│   │   │                              tool_name, args JSONB, result_preview, created_at)
│   │   └── 011_token_usage.py     ← adds prompt_tokens, completion_tokens, total_tokens,
│   │                                  cost_usd (Float) to messages table
│   ├── auth/
│   │   ├── router.py           ← /auth/token, /register, /me
│   │   ├── security.py         ← JWT, bcrypt, get_current_user, require_role
│   │   ├── schemas.py          ← Token, TokenData, RegisterRequest
│   │   └── __init__.py
│   ├── llm/
│   │   ├── service.py          ← generate_stream(), compare_streams(), build_context_messages()
│   │   │                          _needs_file_tools(message) — keyword heuristic, guards tool pass
│   │   │                          tool_call_counts guard: abort if same tool called >3 times/turn
│   │   │                          Agent loop: MAX_TOOL_ITERATIONS=10, forces MODELS["reasoning"]
│   │   │                          when file_ids present AND message needs tools
│   │   │                          ASK_USER_PREFIX detection → yields {type:"ask_user"} + done
│   │   ├── nim.py              ← call() + call_stream() → NIM API
│   │   │                          call_stream() accumulates tool_call deltas in pending dict,
│   │   │                          yields {"__tool_calls__": [...]} on finish_reason=="tool_calls"
│   │   │                          Both accept tools=list|None; include tool_choice:"auto" when set
│   │   ├── tools.py            ← TOOL_SCHEMAS (9 tools) + execute_tool() dispatcher
│   │   │                          ASK_USER_PREFIX = "__ASK_USER__:"
│   │   │                          Every execute_tool() call logs to ToolCallLog via db.flush()
│   │   │                          Tools: list_files, read_file, write_file, create_file,
│   │   │                                 append_to_file, patch_file, search_in_file,
│   │   │                                 search_across_files, ask_user
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
│   │   ├── file_metrics.py     ← FILE_UPLOADS, FILE_DELETES, FILE_CHUNKS, FILE_TOOL_CALLS
│   │   │                          record_upload(), record_delete(), record_chunks(n),
│   │   │                          record_tool_call(name)
│   │   └── token_metrics.py    ← TOKENS_PROMPT, TOKENS_COMPLETION, TOKENS_TOTAL, COST_USD
│   │                              record_tokens(model, prompt, completion, cost) — called on every
│   │                              assistant message save in api/chat.py
│   ├── api/
│   │   ├── chat.py             ← /chat, /chat/stream + helpers:
│   │   │                          ChatRequest, _resolve_model(), _estimate_tokens(),
│   │   │                          _embed_exchange(), _resolve_conversation(),
│   │   │                          _build_stream_context(), _extract_model_params()
│   │   │                          On "done": calculates prompt/completion tokens, cost_usd,
│   │   │                          saves to Message, fires record_tokens(), injects token
│   │   │                          fields into SSE "done" event for frontend immediate display
│   │   ├── files.py            ← all file routes + SSE status stream
│   │   │                          GET /{id}/status/stream — SSE; polls DB + Redis every 0.8s,
│   │   │                          pushes {id, status, progress?} events, terminates on ready/error
│   │   │                          progress (0.0–1.0) from Redis key proc_progress:{file_id}
│   │   ├── conversations.py    ← conversation routes; messages endpoint returns token fields
│   │   │                          (prompt_tokens, completion_tokens, total_tokens, cost_usd)
│   │   ├── memory.py           ← memory routes
│   │   ├── system.py           ← /health, /metrics + ResponseMeta/SuccessResponse/ErrorResponse
│   │   ├── tool_logs.py        ← GET /tool-calls?limit=&conversation_id= — ToolCallLog query
│   │   ├── admin.py            ← admin-only (require_role("admin")):
│   │   │                          GET /admin/users — all users + aggregate token usage + cost
│   │   │                          GET /admin/users/{id}/usage — per-conversation breakdown
│   │   │                          PATCH /admin/users/{id}/active — toggle is_active
│   │   │                          Self-disable blocked (cannot disable own account)
│   │   └── usage.py            ← user self-service:
│   │                              GET /usage — own aggregate (tokens + cost)
│   │                              GET /usage/history — per-conversation breakdown (last 50)
│   ├── services/
│   │   ├── processor.py        ← extract_text(), chunk_text(), extract_url_text(),
│   │   │                          process_file_async(); calls record_chunks(saved) after embed
│   │   │                          Semantic chunker: _split_semantic() → _merge_with_overlap()
│   │   │                            paragraph → sentence → word split; CHUNK_SIZE=1600, OVERLAP=200
│   │   │                            overlap tail sentence-aligned via regex lookbehind
│   │   │                          _extract_docx(): paragraphs + tables (merged-cell dedup via id(cell._tc))
│   │   │                          _extract_excel(): openpyxl, per-sheet markdown tables, empty rows skipped
│   │   │                          Processing progress: sets Redis proc_progress:{file_id} (0.0→1.0)
│   │   │                            after each chunk embedded; key deleted on completion, TTL=300s
│   │   └── file_service.py     ← save_version(db, file_id) — snapshot before any mutation
│   │                              write_content(db, user_id, file_id, content) → str
│   │                              append_content(db, user_id, file_id, content) → str
│   │                              _fuzzy_replace(content, old, new) → (str, bool)
│   │                                  3-pass: exact → normalized \r\n → stripped edges
│   │                              patch_content(db, user_id, file_id, old, new) → str
│   │                              restore_version(db, user_id, file_id, version_id) → str|None
│   ├── storage/
│   │   └── storage_manager.py  ← save_file() reads in 1MB chunks (not file.read() all-at-once)
│   │                              peak memory for 50MB upload: 1MB not 50MB
│   └── tests/
│       ├── test.py             ← 21 pytest unit tests
│       └── model-list.py
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml ← production override: nginx TLS service, resource limits,
│   │                              redis persistence, no-default passwords (POSTGRES_PASSWORD,
│   │                              GRAFANA_ADMIN_PASSWORD required). Firewall: allow 80/443 only.
│   │                              Usage: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── nginx.conf
│   ├── nginx.frontend.conf
│   ├── nginx.prod.conf         ← TLS termination: HTTP→HTTPS redirect, TLS 1.2/1.3, HSTS,
│   │                              certbot challenge passthrough. Replace "example.com" before deploy.
│   ├── backup.sh               ← pg_dump + gzip → storage/backups/, prunes after KEEP_DAYS (default 7)
│   │                              Usage: ./backup.sh  Restore: gunzip -c <file>.sql.gz | docker compose exec -T postgres psql ...
│   ├── prometheus.yml
│   └── grafana/provisioning/
│       ├── datasources/
│       │   ├── prometheus.yml    ← Prometheus datasource (uid: prometheus)
│       │   └── postgres.yml      ← PostgreSQL datasource (uid: postgres); reads POSTGRES_USER/PASSWORD/DB
│       │                            from Grafana container env; used by stat panels 19-22 for persistent totals
│       └── dashboards/
│           ├── dashboard.yml
│           └── nim-gateway.json  ← 24-panel dashboard
└── frontend/
    ├── vite.config.js          ← /api proxy → localhost:8000
    ├── package.json            ← react-markdown + remark-gfm installed
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
| GET | `/files/{id}/status` | JWT | {id, status} — one-shot poll |
| GET | `/files/{id}/status/stream` | JWT | SSE stream of status updates until ready/error |
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
| GET | `/tool-calls` | JWT | ToolCallLog; ?limit=&conversation_id= |
| GET | `/usage` | JWT | own aggregate token usage + cost |
| GET | `/usage/history` | JWT | per-conversation token breakdown (last 50) |
| GET | `/admin/users` | JWT (admin) | all users + aggregate usage |
| GET | `/admin/users/{id}/usage` | JWT (admin) | per-conversation breakdown for user |
| PATCH | `/admin/users/{id}/active` | JWT (admin) | toggle is_active; blocks existing tokens immediately |
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
  → _needs_file_tools(message) keyword check — skip tools for conversational messages
  → if tools needed: generate_stream() forces MODELS["reasoning"] (70B — only reliable tool caller)
  → tools = TOOL_SCHEMAS passed to call_stream()
  → nim.py accumulates tool_call deltas, yields {"__tool_calls__": [...]} on finish_reason=="tool_calls"
  → service.py execute_tool() dispatcher → tools.py implementation
  → execute_tool() logs every call to ToolCallLog (db.flush)
  → yield SSE {type:"tool_call", name, args} + {type:"tool_result", name, content[:500]}
  → tool result appended as role:"tool" message, loop continues (max 10 iterations)
  → ask_user detected: yield {type:"ask_user", question} + done → return (ends loop)
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
| `search_across_files` | query | Semantic top-10 chunks across ALL attached files |
| `ask_user` | question | Pause loop, show amber clarification card, wait for reply |

### System Prompt Rules (injected when files attached)
- File IDs listed explicitly so model never guesses UUIDs
- ONLY use tools when user explicitly asks to read/edit/write/search/create files
- Conversational messages → respond normally, NO tool calls
- To ADD content → use `append_to_file`
- To EDIT specific passage → `read_file` then `patch_file`
- To REWRITE whole file → `write_file` with complete content
- After any write/append/patch/create → respond immediately, do NOT read back to verify
- Never call same tool more than twice in single turn

### Tool Loop Guards
- **Keyword heuristic** (`_needs_file_tools`): tools only passed if message contains file-op words (read, write, edit, find, fix, document, content, …). Conversational messages skip tools entirely.
- **Repetition guard**: `tool_call_counts` dict per turn — if same tool called >3 times, abort with error
- **Iteration cap**: `MAX_TOOL_ITERATIONS = 10`

### SSE Events Yielded
- `{type:"tool_call", name:"read_file", args:{file_id:"..."}}`
- `{type:"tool_result", name:"read_file", content:"first 500 chars of result"}`
- `{type:"ask_user", question:"..."}`
- Frontend renders ⚙ toolname pill per call, expandable to show result
- `ask_user` renders amber clarification card in AI bubble

### Tool Audit Log
- `ToolCallLog` table: every `execute_tool()` call stored (user_id, conv_id, tool_name, args JSONB, result_preview)
- `GET /tool-calls?limit=&conversation_id=` — paginated history
- Frontend: 🔧 Log button in header → slide-in panel, filterable by current conversation or all

### Tool Implementation Notes
- All write ops go through `services/file_service.py` — single source of truth
- `_fuzzy_replace`: 3-pass: exact match → normalized `\r\n→\n` → stripped edges
- Every mutation calls `save_version()` before writing (auto version history)
- After write: delete FileChunk rows, set status="uploaded", commit, fire `process_file_async`
- `search_across_files`: gets all conv file_ids → embed query → `retrieve_from_files(top_k=10)`

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
1. POST /files/upload → `storage/files/` (1MB chunked read) → `process_file_async` background task
2. `extract_text()` → `chunk_text()` → embed each → save FileChunk rows
3. Status: `uploaded` → `processing` → `ready` (or `error`)
4. `record_chunks(saved)` called after embedding
5. Supported: PDF (pypdf), DOCX (python-docx + tables), Excel XLSX/XLS (openpyxl), plain text/code/markdown

### Chunking (`services/processor.py`)
- CHUNK_SIZE=1600 chars, CHUNK_OVERLAP=200
- `_split_semantic(text)`: paragraph (`\n\n`) → sentence (`(?<=[.!?])\s+`) → word split
  - Each pass only triggers if previous boundary wasn't small enough
- `_merge_with_overlap(units, size, overlap)`: greedy merge; on flush, tail aligned to next sentence start via `(?<=[.!?\n])\s*\S` regex
- Result: chunks end at natural boundaries; overlap starts at sentence, not arbitrary offset

### Excel & DOCX Tables
- DOCX: `doc.paragraphs` + `doc.tables`; merged cells deduplicated via `id(cell._tc)`; tables formatted as markdown `|` rows
- Excel: `openpyxl` (read_only + data_only); per-sheet, empty rows skipped; sheet name as `## Sheet: …` header
- Both appended after paragraphs; format is RAG-friendly markdown table

### File Version History
- `FileVersion` model: id (UUID), file_id (FK→files CASCADE), version (int), content (text), created_at
- `save_version()` called before every mutation (write/append/patch/restore)
- API: GET /files/{id}/versions, GET /versions/{vid}, POST /versions/{vid}/restore
- Frontend: Versions tab in file viewer modal, Restore button per version

### File Service (`services/file_service.py`)
- Central logic for all file mutations — tools.py and api/files.py both call this
- `write_content`: save_version → write → delete chunks → commit → re-embed
- `append_content`: save_version → open "a" → `\n\n` separator → delete chunks → commit → re-embed
- `patch_content`: read → fuzzy_replace → if not found: error → save_version → write → re-embed
- `restore_version`: get FileVersion → call write_content(v.content)
- `_fuzzy_replace`: exact → `\r\n` normalized → stripped edges (3-pass fallback)

### Processing Status Stream
- `GET /files/{id}/status/stream` — SSE endpoint (replaces polling)
- Server: `db.expire(f) + db.refresh(f)` every 0.8s; also reads `proc_progress:{file_id}` from Redis
- Pushes `data: {id, status, progress?}\n\n` — `progress` (0.0–1.0) only present during "processing"
- Terminates automatically when status reaches `ready` or `error`
- Frontend: per-file `fetch` with `AbortController` stored in `statusStreamsRef`; streams opened for processing files when panel is open, all aborted on panel close

### Observability (`observability/file_metrics.py`)
- `file_uploads_total` Counter — incremented in POST /files/upload
- `file_deletes_total` Counter — incremented in DELETE /files/{id}
- `file_chunks_total` Counter — incremented after embedding in processor.py
- `file_tool_calls_total` Counter with label `tool` — incremented in file_service.py per operation

### Grafana Dashboard (`docker/grafana/provisioning/dashboards/nim-gateway.json`)
24 panels total. Two datasources intentionally split:
- **Prometheus** (`uid: prometheus`) — rate/timeseries panels; ephemeral (resets on restart)
- **PostgreSQL** (`uid: postgres`) — total/aggregate stat panels; persistent, matches frontend

| Panels | Datasource | Why |
|--------|-----------|-----|
| 1-17, 23-24 | Prometheus | Rate queries, time series, needs scrape history |
| 19-22 | PostgreSQL | All-time totals — must survive container restarts |

Panel layout:
- Panels 1-4: stat row (requests, success rate, cache hit rate, errors)
- Panels 5-6: request rate timeseries, latency p50/p95/p99
- Panels 7-8: model usage rate, model latency p50
- Panels 9-10: cache hits/misses, fallbacks + circuit breaker trips
- Panel 11: row divider "File Knowledge Base"
- Panels 12-15: stat row (uploads total, deletes total, chunks total, tool calls total)
- Panel 16: file uploads/deletes/chunks rate per minute timeseries
- Panel 17: AI tool calls by tool name timeseries
- Panel 18: row divider "Token Usage & Cost"
- Panels 19-22: stat row (prompt tokens total, completion tokens total, total tokens, cost USD) — **PostgreSQL**
- Panel 23: token usage by model timeseries (prompt + completion rate/min) — Prometheus
- Panel 24: estimated cost by model timeseries ($/hr) — Prometheus

### Frontend Files Panel (`Chat.jsx`)
- 📎 button in header — amber + count when files attached
- 2 tabs: Library / Attached
- Library per-file: status badge, filename (or inline rename input), ✎ rename, 👁 view, ⬇ download, +/✓ attach, 🗑 delete
- Attached per-file: status badge, filename, 👁 view, ✕ detach
- Processing status: SSE stream per file (not polling); streams close on ready/error
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

## Frontend

### Chat.jsx — Key Features
- AI responses rendered with `react-markdown` + `remark-gfm` (installed)
  - Streaming: raw `<p>` with blinking cursor
  - Done: `<ReactMarkdown>` in `.md-body` div with scoped CSS
  - User messages and errors stay plain text
- Compare mode: same streaming/done split per model card
- 🔧 Log button → tool call history panel (slide-in, filter by conv or all)
- `ask_user` event → amber clarification card in AI bubble ("NEEDS CLARIFICATION")
- Per-bubble token display: `{totalTokens} tok · $x.xxxxx` shown below model tag when done
  - Live (streaming): tokens from SSE "done" event; loaded (history): from messages endpoint
- `$ Usage` button in header → slide-in panel showing aggregate `/api/usage` data:
  - Messages, prompt tokens, output tokens, total tokens, estimated cost; refresh button

### Tool Log Panel
- State: `toolLogOpen`, `toolLogs`, `toolLogsLoading`
- Loads from `GET /tool-calls?conversation_id=&limit=100`
- Reload button + filter pills (This conversation / All)
- Per-row: tool name (purple), timestamp, args summary, result preview

### ask_user Flow
1. Model calls `ask_user(question="...")` tool
2. Backend: `execute_tool` returns `__ASK_USER__:<question>`
3. `service.py` detects prefix → yields `{type:"ask_user", question}` SSE event + done → returns
4. Frontend SSE handler: sets `m.askUser = question` on message
5. Render: amber card with "NEEDS CLARIFICATION" label + question text
6. User replies normally in input → next message resumes with full context

### Markdown CSS (`.md-body` scoped, injected via `<style>` tag)
Covers: `p`, `h1-h4`, `code` (inline + block `pre`), `ul/ol/li`, `blockquote`, `table/th/td`, `a`, `strong`, `em`, `hr`

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
| Rate limit (chat) | 15 req / 60s per user | `api/chat.py` |
| Cache bypass | history / model_override / model_params / system_prompt / file_chunks | `service.py` |
| Embedding timeout | 15s | `llm/embeddings.py` |
| Memory write lock | pg_advisory_xact_lock(user_id) | `summarizer.py` |
| Max tool iterations | 10 | `llm/service.py:MAX_TOOL_ITERATIONS` |
| Tool repetition guard | >3 calls same tool → abort | `llm/service.py:tool_call_counts` |
| Tool keyword gate | `_needs_file_tools(message)` | `llm/service.py` |
| Max file read (tool) | 100,000 chars | `llm/tools.py:MAX_FILE_READ` |

---

## Token Usage & Admin

### Token Tracking
- Stored on every assistant `Message`: `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`
- Calculated in `api/chat.py` on "done" event (streaming path):
  - `prompt_tokens` = chars÷4 of all context (memory + history + file chunks + message)
  - `completion_tokens` = chars÷4 of full_response
  - `cost_usd` = tokens × `MODEL_PRICING[model]` rates
- Pre-migration messages have NULL token fields — expected

### Model Pricing (`config.py:MODEL_PRICING`)
Rates in $/1M tokens — verify at build.nvidia.com/explore/llm:
| Model | Input | Output |
|-------|-------|--------|
| `meta/llama-3.1-8b-instruct` | $0.10 | $0.10 |
| `deepseek-ai/deepseek-v4-flash` | $0.20 | $0.60 |
| `meta/llama-3.3-70b-instruct` | $0.77 | $0.77 |

### Admin Endpoints (`api/admin.py`)
- Require `role="admin"` — uses `require_role("admin")` from `auth/security.py`
- `GET /admin/users` — list all users with: id, username, role, is_active, message_count, prompt/completion/total tokens, cost_usd
- `GET /admin/users/{id}/usage` — per-conversation breakdown for user
- `PATCH /admin/users/{id}/active` — toggle is_active; self-disable blocked
- Disable effect: immediate — `get_current_user` checks `is_active` on every request

### User Self-Service (`api/usage.py`)
- `GET /usage` — own aggregate: message_count, prompt/completion/total tokens, cost_usd
- `GET /usage/history` — per-conversation breakdown, last 50 conversations

---

## Prometheus Metrics
| Metric | Type | Labels | Recorded in |
|--------|------|--------|-------------|
| `api_requests_total` | Counter | `status` | `api/chat.py` |
| `api_errors_total` | Counter | `type` | `api/chat.py` |
| `cache_hits_total` | Counter | — | `cache.py` |
| `cache_misses_total` | Counter | — | `cache.py` |
| `cache_writes_total` | Counter | — | `cache.py` |
| `model_usage_total` | Counter | `model` | `api/chat.py` |
| `model_latency_seconds` | Histogram | `model` | `api/chat.py` |
| `request_latency_seconds` | Histogram | — | `api/chat.py` |
| `ai_request_latency_seconds` | Histogram | — | `api/chat.py` |
| `fallback_total` | Counter | — | `service.py` |
| `circuit_breaker_trips_total` | Counter | — | `metrics.py` |
| `file_uploads_total` | Counter | — | `api/files.py` |
| `file_deletes_total` | Counter | — | `api/files.py` |
| `file_chunks_total` | Counter | — | `services/processor.py` |
| `file_tool_calls_total` | Counter | `tool` | `services/file_service.py` |
| `tokens_prompt_total` | Counter | `model` | `observability/token_metrics.py` |
| `tokens_completion_total` | Counter | `model` | `observability/token_metrics.py` |
| `tokens_total` | Counter | `model` | `observability/token_metrics.py` |
| `estimated_cost_usd_total` | Counter | `model` | `observability/token_metrics.py` |

---

## Docker Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn |
| frontend | 3000 | nginx serving React build |
| postgres | 5432 | `pgvector/pgvector:pg16` |
| redis | 6379 | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s |
| grafana | 3001 | admin/admin, auto-provisioned 24-panel dashboard |
| metrics-worker | — | `python -m observability.metrics_worker` |

---

## Known Issues
- No integration tests — `/chat` endpoint not covered without live NIM API
- `passlib` deprecation warning for `crypt` on Python 3.13+ — harmless on 3.11
- Embedding latency (~100-300ms) adds to stream start time
- File RAG requires explicit attachment (Library → + button); upload alone is not enough
- File context only injected when `req.conversation_id` is set — first message of new conv won't have it
- AI tool loop forces 70B when file_ids present + `_needs_file_tools` passes — cannot override to smaller model for file ops
- `_needs_file_tools` is keyword-based — may miss implicit file requests (e.g. "look at my notes")
- Token counts on existing messages (pre-migration 011) are NULL — only new messages have data
- Token pricing hardcoded in `config.py:MODEL_PRICING` — verify rates at build.nvidia.com/explore/llm
- Token estimates use chars÷4 (rough); real counts require tiktoken or NIM usage field
- Processing progress (Redis `proc_progress:*`) shows 0.0 briefly before first chunk embeds
- DOCX table extraction appends tables after all paragraphs (not interleaved by document order)
- Prometheus counters reset on container restart — rate panels (23-24) lose history; stat panels (19-22) are unaffected (PostgreSQL)
- `$ Usage` panel shows current user only; no admin view in frontend (admin must use `/admin/users` API directly)

---

## Possible Next Features

Suggestions only — not committed. Ask for specs before implementing any.

### UX / Frontend
- **Conversation search** — sidebar filter by title/keyword; backend `GET /conversations?q=`
- **Message editing** — resend user message with edited content; truncate conversation to that point
- **Conversation export** — download as markdown or JSON; `GET /conversations/{id}/export`
- **Drag-and-drop upload** — drop files anywhere on chat area (no panel required)
- **Keyboard shortcuts** — `Ctrl+Enter` to send, `Ctrl+K` to search convs, `Esc` to close panels
- **Mobile layout** — sidebar collapses to hamburger; input bar stacks vertically
- **Cost budget alerts** — user-configurable cap; toast warning + optional hard block when exceeded
- **Notification on memory update** — subtle flash or badge when background memory write completes
- **Admin frontend panel** — table of users + usage + enable/disable toggle; currently API-only

### RAG / Memory
- **Real token counting** — replace chars÷4 with `tiktoken` or NIM's usage field from API response
- **Hybrid search (BM25 + vector)** — full-text fallback when vector similarity is low; needs `pg_trgm` or `tsvector`
- **File deduplication** — SHA256 before storage; skip re-embed if hash exists
- **Re-embed on model change** — if `MODEL_EMBEDDING` changes, old chunks are stale; migration tool needed
- **Per-conversation memory** — separate memory sheet per conversation, not just per user
- **Graph memory** — entities + relationships extracted from conversations; richer than flat key-value

### Token / Cost
- **Per-user cost caps** — `User.cost_limit_usd`; check on every request, return 402 when exceeded
- **Budget dashboard** — Grafana panels per user (needs PostgreSQL queries with user_id group-by)
- **Monthly rollup** — aggregate table for historical cost analysis beyond Prometheus window

### Observability / Admin
- **User activity timeline** — admin view: last N messages per user with timestamps + models
- **Memory system metrics** — Prometheus counters for memory updates, cache hits/misses on RAG
- **Grafana alerts** — alert rules on error rate >5%, latency p95 >10s, cost spike
- **Usage CSV export** — `GET /admin/export/usage.csv`; admin-only

### Infrastructure / Reliability
- **Real token counts from NIM** — parse `usage` field from non-streaming response; streaming requires accumulation
- **pgBouncer** — connection pooling for high-concurrency deployments
- **Prometheus remote write** — persist metrics across restarts; heavy but fixes rate panel reset issue
- **Health check improvements** — `/health` currently minimal; add NIM API ping, embedding ping, Redis ping
- **Automated backup verification** — weekly restore test to temp DB; alert on failure

### Security (lowest priority — system is home/LAN-deployed)
- **Per-endpoint rate limits** — currently only `/chat` is limited; `/files/upload` and `/files/ingest-url` unprotected
- **Prompt injection detection** — heuristic or classifier before passing user input to model
- **API key auth** — alternative to JWT for programmatic/script access; `User.api_key` column
- **CORS lockdown** — currently open; restrict to known frontend origin in production
- **OpenAI-compatible endpoint** — `POST /v1/chat/completions` wrapper for tool compatibility

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

# Production deploy (Cloudflare Tunnel handles TLS — nginx.prod.conf not needed for home use)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Backup DB
./docker/backup.sh
# Restore: gunzip -c <file>.sql.gz | docker compose exec -T postgres psql -U scylla nimrouter

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
