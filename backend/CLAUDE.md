# Backend Reference

## Structure
```
backend/
├── main.py                 ← app factory: lifespan, middleware, router includes
├── config.py               ← env vars, REQUIRE_INVITE, MODEL_PRICING, _int_env()
├── models.py               ← ORM (see Key Models below)
├── alembic/versions/       ← 026 migrations; latest: 026_system_config.py
├── auth/                   ← JWT, bcrypt, invite validation, Default workspace on register
├── llm/
│   ├── service/context.py  ← _needs_file_tools() + _FILE_OP_KEYWORDS; workspace_memory + graph_context injection
│   ├── service/stream.py   ← MAX_TOOL_ITERATIONS=10; priority: image→override→file_tools(70B)→router
│   ├── nim.py              ← NIM API; accumulates tool_call deltas; yields __tool_calls__ + __usage__
│   ├── tools.py            ← 10 TOOL_SCHEMAS + execute_tool(); logs ToolCallLog on every call
│   ├── graph_memory.py     ← extract_and_store(); query_context(limit=50, min_score=0.5); query_by_term(limit=10, min_score=0.5)
│   ├── router.py           ← keyword classify() + route()
│   ├── circuit_breaker.py  ← threshold=3, cooldown=30s
│   ├── embeddings.py       ← embed(text, input_type) → list[float]; timeout=15s
│   ├── retriever.py        ← hybrid vector+BM25 RRF (k=60); _FETCH_N=20 per side
│   ├── summarizer.py       ← update_memory() + _update_workspace_memory() + compress_history()
│   └── agency.py           ← generate_proactive_suggestion(); generate_insight_job (ARQ)
├── cache/                  ← Redis primary + LRU fallback; CACHE_VERSION=v2
├── core/                   ← db.py, redis_client.py, arq_pool.py, logger.py, neo4j_client.py
├── rate_limiter/           ← sliding-window; check_model_rate(model, username); fails open
├── observability/          ← Prometheus counters/histograms; see prom_metrics.py
├── api/
│   ├── chat/               ← /chat + /chat/stream; auto-title after 2nd msg; cost cap check
│   ├── workspaces.py       ← /workspaces CRUD + memory routes
│   ├── files/              ← upload, ingest-url, search, versions, workspace assign; sha256 dedup
│   ├── conversations.py    ← list (?q= full-text), export (md/json), PATCH, file attach/detach
│   ├── admin.py            ← require_role("admin"); users, cost-limit, audit-log, re-embed; _audit() helper
│   ├── graph.py            ← GET /graph/stats → {available, entities, relations}; scoped by user_id
│   ├── compat.py           ← POST /v1/chat/completions (OpenAI-compat; JWT or API key)
│   ├── templates.py        ← prompt templates CRUD + /apply/{conv_id}
│   ├── scheduled_prompts.py ← CRUD + run history + manual trigger
│   └── usage.py / memory.py / system.py / tool_logs.py
├── services/
│   ├── processor.py        ← extract→chunk(1600/200 overlap)→concurrent embed; ARQ or inline
│   ├── arq_worker.py       ← max_tries=4; retries 5s/30s/120s; generate_insight_job every 10 msgs; re_embed_batch_job
│   └── re_embed.py         ← check_and_queue_re_embed() on startup; queue_re_embed_force(); batches of 100
│   ├── file_service.py     ← write/append/patch/restore; _fuzzy_replace 3-pass; save_version before mutate
│   └── scheduler_worker.py ← APScheduler cron runner
├── storage/storage_manager.py ← SHA256 while streaming; save_file→4-tuple, save_text→3-tuple
└── tests/test.py           ← 21 pytest unit tests
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
- **Chat**: POST /chat · /chat/stream · /v1/chat/completions
- **Files**: upload, ingest-url, search, list, workspaces; /{id}: content, status[/stream], download, rename, workspace; versions
- **Conversations**: list (?q= ?workspace_id=), export, messages, PATCH, delete; files attach/detach
- **Workspaces**: CRUD; /{id}/conversations · files · memory
- **Admin**: users list/usage; active toggle; cost-limit; audit-log (?action=&target_user_id=); re-embed
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
3. [GRAPH CONTEXT] — Neo4j entity/relation context (when memory_enabled + Neo4j up); limit=8 entities
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
- Retrieval: vector + BM25 parallel → RRF merge (k=60); fallback to pure vector
- Status SSE: polls `db.refresh` + Redis `proc_progress:{file_id}` every 0.8s → terminates on ready/error
- `file_service`: save_version before every mutation; `_fuzzy_replace`: exact → `\r\n` norm → stripped edges

---

## Admin / Cost
- Cost cap: rolling window (`cost_window_days`, default 30, null=all-time) → 402 on exceed; label in error e.g. `$4.23 / $5.00 30d`
- Audit actions: `user.active.enabled/disabled` · `user.cost_limit.set/removed` (JSONB with prev+new values)
- Self-disable blocked; `is_active` checked on every `get_current_user`
- API key: JWT first, DB key fallback in `auth/security.py`
- Model pricing (`config.py`): llama $0.10/$0.10 · coder $0.20/$0.60 · reasoning $0.77/$0.77 per 1M tokens

---

## Non-obvious Invariants
- pgBouncer transaction mode → `prepared_statement_cache_size=0` required (`core/db.py`)
- Cache bypass when: file_chunks / image_b64 / model_params present; v2 key = msg+model+history[-4]+sysprompt
- ARQ: api enqueues → arq-worker consumes; inline fallback when pool unavailable (scheduler_worker path)
- SHA256 dedup returns existing file + `"duplicate": true` — no re-upload to disk
- `passlib` crypt warning on Python 3.13+ — harmless on 3.11

---

## HANDOFF Protocol

### Role
Worker for `backend/` only. Root plans; this agent implements.

**Scope rule:** If a task belongs outside `backend/` — do not implement it. Instead:
1. Note it in `HANDOFF.md` under the correct dir section (`## frontdir` or `## dockdir`)
2. Pass the file to that dir when done with backend tasks

**Root escalation:** Do not edit root-level files directly. Pass back to root (`../HANDOFF.md`, status: needs-root) for any changes to:
`.env` · `.env.example` · `.gitignore` · `.dockerignore` · `CLAUDE.md` (root) · `README.md` · `ROADMAP.md`
or any file not clearly owned by `backend/`, `frontend/`, or `docker/`.

---

On session start — check if `backend/HANDOFF.md` exists:
```bash
ls HANDOFF.md 2>/dev/null && echo "YOUR TURN" || echo "no handoff"
```

If it exists:
1. Read `## backdir` section — Tasks + any Recorded facts from prior agents
2. Execute all tasks (check off as done)
3. Fill `### Recorded` with concrete facts for the next agent:
   - Exact endpoint: method + path + request body shape + response shape
   - New env vars (name + purpose)
   - New SSE event types/fields
   - New DB columns or migration numbers
4. **Update `backend/CLAUDE.md`** — add any new files, routes, models, tools, or invariants introduced by the feature
5. Append a History row
6. Move file to next dir:
   ```bash
   mv HANDOFF.md ../frontend/HANDOFF.md   # or ../docker/HANDOFF.md or ../HANDOFF.md
   ```

Write terse, precise Recorded facts — next agent has no backend context.
