# Backend Reference

## Structure
```
├── main.py                 — lifespan, middleware, router includes
├── config.py               — env vars loaded from ../.env via find_dotenv()
├── models/                 — ORM (20 classes across 8 sub-modules)
│   ├── __init__.py         — re-exports all models
│   ├── workspace.py        — Workspace, WorkspaceMemory
│   ├── auth.py             — Invitation
│   ├── user.py             — User, UserInsight, AdminAuditLog, UserMemory, UserMemoryVersion
│   ├── file.py             — File, FileChunk, FileVersion
│   ├── chat.py             — Conversation, Message, MessageEmbedding, ConversationFile
│   ├── tools.py            — ToolCallLog
│   ├── prompts_scheduled.py — PromptTemplate, ScheduledPrompt, ScheduledPromptRun
│   └── system.py           — SystemConfig
├── alembic/versions/       — 030 migrations; latest: 030_chunk_quality.py
├── auth/                   — JWT, bcrypt, API key fallback, invite validation
├── tests/
│   ├── test.py             — 21 unit tests (standalone, no docker)
│   └── retrieval/
│       ├── conftest.py     — shared fixtures, dataset, mock helpers, metric utils
│       └── test_hybrid_eval.py — 26 tests (mock DB, no NIM)
├── llm/
│   ├── service/            — context build, context budget allocator, SSE stream + tool loop (MAX_TOOL_ITERATIONS=10)
│   ├── nim.py              — NIM API call, accumulates tool_call deltas
│   ├── tools/              — 10 tool schemas + execute_tool(); sync I/O via asyncio.to_thread()
│   │   ├── schemas.py      — tool definitions
│   │   ├── executor.py     — execute_tool() dispatch
│   │   ├── file_ops.py     — read/write/append/patch/create file ops
│   │   └── search.py       — search_in_file + search_across_files
│   ├── graph_memory.py     — Neo4j extraction/query + query_by_keywords (stopwords, fulltext, neighborhood expansion); limit=50, min_score=0.5; UNWIND batch writes; Redis cache 60s (USE_REDIS gated)
│   ├── router.py           — keyword classify(), model route(), get_context_limit()
│   ├── circuit_breaker.py  — 3 failures → 30s cooldown
│   ├── embeddings.py       — embed(text, input_type) → list[float]; timeout=15s
│   ├── retriever/          — hybrid vector+BM25 fusion (rrf|weighted); debug param
│   │   ├── fusion.py       — rrf + weighted fusion, score normalization
│   │   ├── queries.py      — SQL query builders for vector + BM25
│   │   ├── main.py         — retrieve() entry point, provenance tracking
│   │   └── attachments.py  — retrieve_from_files() for conversation attachments
│   ├── summarizer/         — memory compression, compaction, workspace memory updates
│   │   ├── prompts.py      — summarization prompt templates
│   │   ├── memory.py       — workspace memory read/write
│   │   ├── history.py      — history summarization
│   │   ├── project.py      — project summary updates
│   │   └── compact.py      — compact_memory() LLM-driven dedup
│   └── agency.py           — proactive suggestions + insight generation (ARQ)
├── cache/                  — Redis primary + LRU fallback; cache-bypass on file/image/model-param
├── core/                   — db (pgbouncer: prepared_statement_cache_size=0), redis, arq, neo4j (get_health; pool size=20, timeout=5s)
├── rate_limiter/           — sliding-window per user + per-model; reuses request.state.current_user
├── observability/          — Prometheus counters/histograms; Redis-stream metrics worker
├── api/
│   ├── chat/
│   │   ├── __init__.py     — combines router + stream_router
│   │   ├── schemas.py      — ChatRequest model
│   │   ├── router.py       — POST /chat (non-streaming)
│   │   ├── stream.py       — POST /chat/stream SSE endpoint + event_generator
│   │   ├── helpers.py      — context build, model resolve, cost cap, conversation resolve
│   │   └── background.py   — auto-title, embed, proactive, token/cost calc
│   ├── workspaces.py       — /workspaces CRUD + memory routes
│   ├── files/              — upload, ingest-url, search, versions, workspace assign; sha256 dedup
│   ├── conversations/      — list (?q=), export, PATCH, delete; file attach/detach
│   │   ├── __init__.py     — combines crud + files sub-routers
│   │   ├── crud.py         — list, messages, PATCH, export, delete
│   │   └── files.py        — attach/detach files
│   ├── admin/              — require_role("admin"); users, cost-limit, audit-log, env mgmt
│   │   ├── __init__.py     — combines all sub-routers
│   │   ├── utils.py        — _audit(), _user_row(), _fetch_user_stats(), _mask()
│   │   ├── users.py        — GET/PATCH user routes
│   │   ├── audit.py        — GET /audit-log
│   │   ├── env.py          — GET/PUT env vars, reload
│   │   └── system.py       — POST /re-embed
│   ├── graph.py / compat.py / templates.py / scheduled_prompts.py / usage.py / memory.py / system.py / tool_logs.py
├── services/
│   ├── processor.py        — extract→chunk→embed; CPU work in asyncio.to_thread()
│   ├── arq_worker.py       — max_tries=4 (5s/30s/120s); insight, re-embed, compact_memory jobs
│   ├── re_embed.py         — batches of 100; triggered on startup or /admin/re-embed
│   ├── file_service.py     — fuzzy-patch, save-version-before-mutate; sync I/O in asyncio.to_thread()
│   └── scheduler_worker.py — APScheduler cron runner; daily memory compaction at 3 AM UTC
├── storage/                — SHA256 streaming write
└── HANDOFF_PROTOCOL.md     — worker handoff protocol (shared from root)
```

---

## Key Models
- **User**: cost_limit_usd/cost_window_days cap, api_key auth, is_active gate
- **File**: sha256_hash dedup `(user_id, hash)`, workspace_id FK SET NULL
- **Message**: content_tsv GIN for full-text search; tracks token + cost
- **SystemConfig**: key/value store — tracks MODEL_EMBEDDING for re-embed triggers
- Others: 15 more in `models/` (chat, file, workspace, memory, tools, scheduled, auth)

---

## ChatRequest
`message` (str, max 2000) · `conversation_id` · `workspace_id` (UUID) · `model_override`
`temperature` (0–2) · `max_tokens` (1–4096) · `top_p` (0–1) · `compare` (bool)
`image_b64` (base64 → forces vision) · `image_mime_type`

---

## AI Agent Tool Loop
- Trigger: any message when `file_ids` non-empty → always forces reasoning model (70B); 8B cannot reliably use tool results
- File tools always available when files attached (not keyword-gated); `_needs_file_tools()` no longer gates tool availability
- Tools: `list_files` · `read_file` (100k cap, capped to 12000 chars in context) · `write_file` · `create_file` · `append_to_file` · `patch_file` (fuzzy) · `search_in_file` · `search_across_files` · `ask_user` · `query_graph` · `write_memory`
- Guards: same tool >3× → abort · MAX_TOOL_ITERATIONS=10 · tool result stored in context capped at 12000 chars (prevents 70B refusal on large repeated reads)
- `ask_user` yields `{type:"ask_user"}` SSE + done → pauses loop; amber card in UI
- `write_memory`: available only on reasoning model when `memory_enabled=True`; requires explicit user instruction ("remember", "save", "store") — NEVER fires on inference or file content; yields `{type:"confirm_write_memory", fact}` SSE + done → pauses loop; green card in UI; user confirms → `POST /api/memory/write`
- `append_to_file`: NEVER used to answer questions; only for explicit "add/append/write to file" requests
- File tool rules in system prompt: write tools banned for informational responses; `search_in_file` preferred over `read_file` for specific section lookups in large files
- `POST /api/memory/write` — body `{fact: str}`, reads existing `UserMemory`, appends fact as new line (trim to 500 chars), snapshots version, bumps version +1, boosts salience +0.1

---

## Memory System
Injection order (build_context_messages):
1. system message — workspace_sysprompt + conv_sysprompt + file list/rules
2. [GRAPH CONTEXT] — Neo4j entity/relation context (when memory_enabled + Neo4j up); limit=50, min_score=0.5; cached in Redis 60s per (user_id, query_text)
3. [GRAPH FACTS] — keyword-triggered neighborhood expansion via query_by_keywords; cached in Redis 60s
4. [USER STATE] — memory_sheet (top 20 facts by salience; conflicted facts suppressed)
5. [WORKSPACE STATE] · [PROJECT STATE]
6. [RELEVANT CONTEXT FROM EARLIER] — cosine top-K retrieved chunks
7. [EARLIER IN THIS CONVERSATION] — history_summary
8. last 10 importance-weighted messages (history)
9. [FILE CONTEXT] — policy["top_k"] chunks (varies: factual=weighted, relational=RRF etc.); fallback top_k=10 sequential; appended last for recency bias
10. current user message

- Triggers: memory update >3000 tok OR every 10 asst msgs; history compression + project summary update >4000 tok OR every 15 total msgs (all_count > 10); auto-title after 2nd msg via `asyncio.create_task`
- Lock: `pg_advisory_xact_lock(user_id)` prevents version races
- Compaction: LLM-driven dedup via `compact_memory()`; creates `UserMemoryVersion` snapshot; queued via ARQ or daily cron at 3 AM UTC
- Context budget: drops lowest-tier sources when estimated tokens exceed `context_window - max_output_tokens - 10%`; re-applied after each tool iteration
- Salience: `UserMemory` has `salience` (float, default 1.0) and `confidence` (float, default 1.0); bumped on every context load via `compute_salience()`, decayed 0.95/cycle during compaction; memory cleared when salience <0.3
- `POST /memory/decay`: manual decay pass; GET /memory returns per-fact `facts` array with per-line scores
- Conflict resolver: `MemoryConflict` table stores `fact_a/fact_b/conflict_type/resolution`; detected post-compaction and via `POST /memory/conflicts/scan`; unresolved facts suppressed from context injection; resolve via `POST /memory/conflicts/{id}/resolve` with strategy `keep_a|keep_b|merge|discard_both`
- Per-fact salience: `UserMemory.fact_saliences` JSONB maps fact text → score; facts sorted high→low before `[USER STATE]` injection (top 20); bumped per-access via `bump_fact_saliences()`; decayed per compaction cycle; low-salience facts dropped first by context budget allocator (tier 1 partial drop before full drop)
- Retrieval re-ranking: retrieved chunks re-scored by `final_score * (1 + memory_salience * 0.05)` after retrieval

---

## Files & Knowledge
- Upload: SHA256 while streaming → dedup `(user_id, hash)` → ARQ job or inline fallback
- Formats: PDF · DOCX (+tables after paragraphs) · XLSX/XLS · text/code/markdown
- Chunks: 1600 chars, 200 overlap, sentence-aligned tail
- Chunk quality states: `upload_status` values are `uploaded|processing|ready|partial|failed|error`; `partial` = some chunks embedded, some failed; `File` has `chunk_total`, `chunk_embedded`, `embed_fail_count`; status reset and counts cleared on file edit
- Retrieval: vector + BM25 parallel → RRF (k=60) or weighted fusion; fallback to pure vector
- Adaptive policy: `classify_query(msg)` in `router.py` returns `factual|relational|temporal|broad`; mapped in `retriever/policy.py` to fusion_mode/alpha/k values (factual=weighted 0.7, relational=RRF, temporal=RRF low-k, broad=weighted 0.3); applied per-query in `_build_stream_context()`; logged with query_type + params; also emitted in `done` SSE event as `query_type` + `src_count` (number of retrieved provenance chunks)
- Status SSE: polls `db.refresh` + Redis `proc_progress:{file_id}` every 0.8s → terminates on ready/error
- `file_service`: save_version before every mutation; `_fuzzy_replace`: exact → `\r\n` norm → stripped edges

---

## Admin / Cost
- Cost cap: rolling window (`cost_window_days`, default 30, null=all-time) → 402 on exceed; label in error e.g. `$4.23 / $5.00 30d`
- Audit actions: `user.active.enabled/disabled` · `user.cost_limit.set/removed` · `env.updated` · `env.reloaded` (JSONB with prev+new values)
- Self-disable blocked; `is_active` checked on every `get_current_user`
- API key: JWT first, DB key fallback in `auth/security.py`
- Model pricing (`config.py`): llama $0.10/$0.10 · coder $0.20/$0.60 · reasoning $0.77/$0.77 per 1M tokens

---

## Non-obvious Invariants
- pgBouncer transaction mode → `prepared_statement_cache_size=0` required (`core/db.py`)
- Cache: early check before context build; v2 key = msg+model+history[-4]+sysprompt; bypassed on image_b64 / model_params / ConversationFile
- ARQ: api enqueues → arq-worker consumes; inline fallback when pool unavailable
- SHA256 dedup: returns existing file + `duplicate: true` — no re-upload
- Sync file I/O + CPU parsing wrapped in `asyncio.to_thread()` (tools.py, file_service.py, processor.py)
- Rate limiter reuses `request.state.current_user` to skip JWT re-decode
- `passlib` crypt warning on Python 3.13+ — harmless on 3.11
- Dotenv admin: `/admin/env` masks sensitive keys; PUT writes `.env` + updates running config; `POST /admin/env/reload` does `importlib.reload(config)`
- `.env` merge script in root CLAUDE.md — adds missing keys from `.env.example` as commented-out
- Debug mode: `retriever.retrieve()` / `retrieve_from_files(debug=True)` returns `(chunks, debug_info)` tuple; `/search?debug=true` returns `{"results": [...], "debug": [...]}`
- Eval harness: `tests/retrieval/test_hybrid_eval.py` — 26 tests, mock DB (AsyncMock), no NIM deps; run with `pytest tests/retrieval/ -v`
- Neo4j indexes created on startup: unique constraint `(user_id, name)`, fulltext `entity_name_ft` on `e.name`, range index `entity_user_id` on `e.user_id`; writes use UNWIND batch (2 round-trips regardless of entity/rel count); graph query results cached in Redis (key `graph:{user_id}:{sha256[:20]}`, TTL 60s, USE_REDIS gated)

---

## HANDOFF Protocol — Quick Reference

- **Role:** backend worker. Do not plan or delegate.
- **Scope:** `backend/` files only. Cross-dir tasks → put in `HANDOFF.md` section, pass file.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## backdir`, execute tasks, fill `### Recorded` (endpoint shapes, env vars, SSE events, DB columns), update this file, append History, `mv HANDOFF.md ../frontend/HANDOFF.md`.
- **Recorded facts:** write terse, precise — next agent has no backend context.

> Full protocol: `../HANDOFF_PROTOCOL.md`
