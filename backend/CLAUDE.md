# Backend Reference

## Structure
```
├── main.py                 — lifespan, middleware, router includes
├── config.py               — env vars loaded from ../.env via find_dotenv()
├── models.py               — ORM (User, File, Message, Conversation, AdminAuditLog, …)
├── alembic/versions/       — 026 migrations; latest: 026_system_config.py
├── auth/                   — JWT, bcrypt, API key fallback, invite validation
├── llm/
│   ├── service/            — context build, SSE stream + tool loop (MAX_TOOL_ITERATIONS=10)
│   ├── nim.py              — NIM API call, accumulates tool_call deltas
│   ├── tools.py            — 10 tool schemas + execute_tool(); sync I/O via asyncio.to_thread()
│   ├── graph_memory.py     — Neo4j entity extraction/query; limit=50, min_score=0.5
│   ├── router.py           — keyword classify() + model route()
│   ├── circuit_breaker.py  — 3 failures → 30s cooldown
│   ├── embeddings.py       — embed(text, input_type) → list[float]; timeout=15s
│   ├── retriever.py        — hybrid vector+BM25 fusion (rrf|weighted); stores provenance per hit
│   ├── summarizer.py       — memory compression + workspace memory updates
│   └── agency.py           — proactive suggestions + insight generation (ARQ)
├── cache/                  — Redis primary + LRU fallback; cache-bypass on file/image/model-param
├── core/                   — db (pgbouncer: prepared_statement_cache_size=0), redis, arq, neo4j
├── rate_limiter/           — sliding-window per user + per-model; reuses request.state.current_user
├── observability/          — Prometheus counters/histograms; Redis-stream metrics worker
├── api/
│   ├── chat/               — /chat + /chat/stream; auto-title, cost-cap, early-cache check
│   ├── workspaces.py       — /workspaces CRUD + memory routes
│   ├── files/              — upload, ingest-url, search, versions, workspace assign; sha256 dedup
│   ├── conversations.py    — list (?q=), export, PATCH, delete; file attach/detach
│   ├── admin.py            — require_role("admin"); users, cost-limit, audit-log, re-embed, dotenv mgmt
│   ├── graph.py / compat.py / templates.py / scheduled_prompts.py / usage.py / memory.py / system.py / tool_logs.py
├── services/
│   ├── processor.py        — extract→chunk→embed; CPU work in asyncio.to_thread()
│   ├── arq_worker.py       — max_tries=4 (5s/30s/120s); insight, re-embed jobs
│   ├── re_embed.py         — batches of 100; triggered on startup or /admin/re-embed
│   ├── file_service.py     — fuzzy-patch, save-version-before-mutate; sync I/O in asyncio.to_thread()
│   └── scheduler_worker.py — APScheduler cron runner
├── storage/                — SHA256 streaming write
└── tests/test.py           — 21 unit tests (standalone, no docker)
```

---

## Key Models (models.py)
- **User**: is_active, cost_limit_usd (null=no cap), cost_window_days (null=all-time), api_key
- **File**: sha256_hash (dedup key), workspace_id UUID FK
- **Message**: content_tsv GENERATED tsvector GIN — full-text search; token + cost fields
- **Conversation**: workspace_id UUID FK SET NULL
- **UserInsight**: id UUID, user_id, content, is_read, created_at
- **AdminAuditLog**: id UUID, admin_id, action str64, target_user_id, detail JSONB, created_at
- **SystemConfig**: key VARCHAR PK, value TEXT, updated_at TIMESTAMPTZ — used for MODEL_EMBEDDING tracking
- Others: FileChunk · FileVersion · UserMemory · MessageEmbedding · UserMemoryVersion · ConversationFile · ToolCallLog · PromptTemplate · ScheduledPrompt · ScheduledPromptRun · Workspace · WorkspaceMemory · Invitation

---

## API Routes (groups — see api/ routers for full signatures)
- **Auth**: token, register, me, me/api-key; invite + invites (admin)
- **Chat**: POST /chat · /chat/stream · /v1/chat/completions; `/chat/stream` `done` event includes `provenance: [{chunk_id, source_id, dense_score, sparse_score, final_score, retrieval_type}]` (deduped from retrieved+file_chunks; `[]` when no RAG)
- **Files**: upload, ingest-url, search (?fusion_mode=&k_dense=&k_sparse=&alpha=), list, workspaces; /{id}: content, status[/stream], download, rename, workspace; versions
- **Conversations**: list (?q= ?workspace_id=), export, messages, PATCH, delete; files attach/detach
- **Workspaces**: CRUD; /{id}/conversations · files · memory
- **Admin**: users list/usage; active toggle; cost-limit; audit-log (?action=&target_user_id=); re-embed; env vars list/get/update/reload
- **Graph**: GET /graph/stats — entity/relation counts for current user (Neo4j)
- **Misc**: health · metrics[/overview|models|latency] · tool-calls · usage[/history] · memory · insights · templates · scheduled-prompts

---

## ChatRequest
`message` (str, max 2000) · `conversation_id` · `workspace_id` (UUID) · `model_override`
`temperature` (0–2) · `max_tokens` (1–4096) · `top_p` (0–1) · `compare` (bool)
`image_b64` (base64 → forces vision) · `image_mime_type`

---

## AI Agent Tool Loop
- Trigger: `_needs_file_tools(message)` keyword gate → forces reasoning model (70B)
- Tools: `list_files` · `read_file` (100k cap) · `write_file` · `create_file` · `append_to_file` · `patch_file` (fuzzy) · `search_in_file` · `search_across_files` · `ask_user` · `query_graph`
- Guards: same tool >3× → abort · MAX_TOOL_ITERATIONS=10
- `ask_user` yields `{type:"ask_user"}` SSE + done → pauses loop; amber card in UI

---

## Memory System
Injection order:
1. workspace_sysprompt merged with conv_sysprompt + file list
2. [USER STATE] · [WORKSPACE STATE] · [PROJECT STATE]
3. [GRAPH CONTEXT] — Neo4j entity/relation context (when memory_enabled + Neo4j up); limit=50, min_score=0.5
4. [RELEVANT CONTEXT] cosine top-K · [EARLIER IN CONV] history_summary
5. last 10 importance-weighted messages
6. [FILE CONTEXT] top-5 chunks — last for recency bias
7. current message

- Triggers: >3000 tok OR every 10 asst msgs; project summary >4000 OR every 15
- Auto-title: after 2nd message → llama "6 words or fewer" via `asyncio.create_task`
- Lock: `pg_advisory_xact_lock(user_id)` prevents version races
- ws_sysprompt precedence: merged as `ws + "\n\n" + conv` when both set

---

## Files & Knowledge
- Upload: SHA256 while streaming → dedup `(user_id, sha256_hash)` → ARQ job or inline fallback
- Formats: PDF · DOCX (+tables after paragraphs) · XLSX/XLS · text/code/markdown
- Chunks: 1600 chars, 200 overlap, sentence-aligned tail
- Retrieval: vector + BM25 parallel → RRF (k=60) or weighted fusion; params: fusion_mode (rrf|weighted), k_dense, k_sparse (1-100), alpha (0-1); fallback to pure vector
- Weighted mode: normalizes raw cosine sim + ts_rank to [0,1], final = alpha*dense + (1-alpha)*sparse
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

---

## HANDOFF Protocol — Quick Reference

- **Role:** backend worker. Do not plan or delegate.
- **Scope:** `backend/` files only. Cross-dir tasks → put in `HANDOFF.md` section, pass file.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## backdir`, execute tasks, fill `### Recorded` (endpoint shapes, env vars, SSE events, DB columns), update this file, append History, `mv HANDOFF.md ../frontend/HANDOFF.md`.
- **Recorded facts:** write terse, precise — next agent has no backend context.

> Full protocol: `../HANDOFF_PROTOCOL.md`
