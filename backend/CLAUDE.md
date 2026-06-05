# Backend Reference

## Structure
```
├── main.py                 — lifespan, middleware, router includes
├── config.py               — env vars loaded from ../.env via find_dotenv()
├── agent/                  — canvas architecture (node registry, Neo4j CRUD, boot diagnostics)
│   ├── __init__.py
│   ├── node.py             — Node dataclass + 11-type registry
│   ├── canvas_graph.py     — Neo4j CanvasNode CRUD, canvas cache, scratchpad read/write
│   └── boot.py             — agent_boot() health checks, BootReport, format_boot_log()
├── models/                 — ORM (21 classes: Invitation, User, UserInsight, AdminAuditLog, UserMemory, MemoryConflict, UserMemoryVersion, UserBehaviorProfile, UserGoal, File, FileChunk, FileVersion, Conversation, Message, MessageEmbedding, ConversationFile, ToolCallLog, PromptTemplate, ScheduledPrompt, ScheduledPromptRun, SystemConfig)
├── alembic/versions/       — 037 migrations; latest: 037_drop_workspaces.py (removed the workspace layer)
├── auth/                   — JWT, bcrypt (direct, no passlib), API key fallback, invite validation
├── tests/
│   └── test.py + retrieval/conftest.py + test_hybrid_eval.py — 47 tests, mock DB, no NIM
├── llm/
│   ├── service/            — context build, context budget allocator, SSE stream + tool loop (MAX_TOOL_ITERATIONS=20)
│   ├── nim.py              — NIM API call, accumulates tool_call deltas
│   ├── tools/              — 18 tool schemas + execute_tool(); sync I/O via asyncio.to_thread()
│   │   └── schemas.py, executor.py, file_ops.py, search.py
│   ├── graph_memory.py     — Neo4j extraction (70B model) + query_by_keywords; entity caps: _MAX_ENTITY_NAME_LEN=200, _MAX_ENTITIES_PER_CALL=30, _MAX_RELS_PER_CALL=60, _MAX_USER_ENTITIES=500 (evicts oldest by updated_at); cache key SHA256[:32]; _cache_del_user() busts on write; skips if compact:running:{user_id} Redis lock held; MERGE SET preserves specific type over OTHER
│   ├── router.py / circuit_breaker.py / embeddings.py — classify, circuit, embed
│   ├── retriever/          — hybrid vector+BM25 fusion (rrf|weighted); debug param; fusion.py, queries.py, main.py, attachments.py
│   ├── summarizer/         — memory compression, compaction; prompts.py, memory.py, history.py, project.py, compact.py
│   └── agency.py           — proactive suggestions + insight generation (ARQ)
├── cache/                  — Redis primary + LRU fallback; cache-bypass on file/image/model-param
├── core/                   — db (pgbouncer: prepared_statement_cache_size=0), redis, arq, neo4j (get_health; pool size=20, timeout=5s)
├── rate_limiter/           — sliding-window per user + per-model; reuses request.state.current_user; logs warning on fail-open (Redis down)
├── observability/          — Prometheus counters/histograms; Redis-stream metrics worker; multiprocess mode via PROMETHEUS_MULTIPROC_DIR
├── api/
│   ├── chat/
│   │   ├── __init__.py     — combines router + stream_router
│   │   ├── schemas.py      — ChatRequest model
│   │   ├── router.py       — POST /chat (non-streaming)
│   │   ├── stream.py       — POST /chat/stream SSE endpoint + event_generator; status="partial" for mid-stream breaks (STREAM_INTERRUPTIONS counter); ALL_MODELS_FAILED counter; emits `canvas_update` event after any `canvas_*` tool result (frontend re-fetches GET /canvas/graph); saves `pending_question` from `ask_user` event as assistant message content; injects node_inventory with supplemental prompt instructions
│   │   ├── helpers.py      — context build, model resolve, cost cap; auto-resolves expired MemoryConflicts (keep_a); time-based fact salience decay in ranking (not persisted)
│   │   └── background.py   — auto-title, embed, proactive, token/cost calc; _auto_title uses atomic UPDATE...WHERE title=:default (no TOCTOU race)
│   ├── files/              — upload, ingest-url, search, versions; sha256 dedup
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
│   ├── canvas.py           — REST bridge for AI canvas graph: GET /canvas/graph · POST /canvas/nodes · PATCH /canvas/nodes/{id} · DELETE /canvas/nodes/{id} · POST /canvas/wire · DELETE /canvas/wire · GET /canvas/global (returns-or-creates JARVIS conversation, title="JARVIS"); all auth-gated; calls agent/canvas_graph.py; 400 on ValueError (bad type/port), 404 on missing node
│   ├── graph.py            — /graph/stats, /health, /sample (?limit=1-200, ?entity_type=); DELETE /graph/entities/{name}; POST /graph/prune (removes long names + stale OTHER-type entities >7 days)
│   ├── system.py           — /health, /metrics, /hardware + /system/hardware alias (both serve CPU/RAM/GPU/disk/uptime — psutil + pynvml); probe_models_on_startup() pings all MODELS, pre-trips circuit on failure
│   ├── memory.py           — GET /memory returns active_conflicts count; scan_conflicts sets expires_at=+7d; conflicts auto-resolved keep_a after expiry
│   ├── export.py            — GET /export/full; builds ZIP in memory with conversations/files/memory/graph data
│   ├── search.py            — GET /api/search unified search; fans out to files/conversations/memory/graph via asyncio.gather
│   ├── goals.py             — CRUD for UserGoal; status filter, conversation linking
│   ├── scheduled_prompts.py — CRUD for user-defined automated prompts; schedule alias support (daily/weekly/monthly); POST /run trigger
│   ├── compat.py / templates.py / usage.py / tool_logs.py
├── services/
│   ├── processor.py        — extract→chunk→embed; CPU work in asyncio.to_thread()
│   ├── arq_worker.py       — _MAX_TRIES=4 (5s/30s/120s); ARQ_JOB_FAILED counter on final failure for all jobs; process_file_job sets upload_status="error" on final failure
│   ├── re_embed.py         — batches of 100; triggered on startup or /admin/re-embed
│   ├── file_service.py     — fuzzy-patch, save-version-before-mutate; sync I/O in asyncio.to_thread()
│   └── scheduler_worker.py — APScheduler cron runner; daily memory compaction at 3 AM UTC; backup via BACKUP_SCHEDULE env (default 2 AM UTC)
├── storage/                — SHA256 streaming write
├── requirements.txt        — added psutil + nvidia-ml-py for /hardware endpoint
└── HANDOFF_PROTOCOL.md     — worker handoff protocol (shared from root)
```

---

## Key Models
- **User**: cost_limit_usd/cost_window_days cap, api_key auth, is_active gate
- **File**: sha256_hash dedup `(user_id, hash)`
- **Message**: content_tsv GIN for full-text search; tracks token + cost; `token_estimate` (bool, nullable) — true = character-heuristic backfill (migration 032), null = real NIM data
- **SystemConfig**: key/value store — tracks MODEL_EMBEDDING for re-embed triggers
- Others: more in `models/` (chat, file, memory, tools, scheduled, auth)
- **UserBehaviorProfile**: one row per user, JSONB `profile` with `query_types / topic_keywords / tools_used / models_used / total_messages`; updated via ARQ `update_behavior_profile_job` post-reply; feeds `generate_user_insight()`; migration 033
- **UserMemory**: added `agent_scratchpad` JSONB (nullable) in migration 036 — append-only merge canvas writes

---

## ChatRequest
`message` (str, max 2000) · `conversation_id` · `model_override`
`temperature` (0–2) · `max_tokens` (1–4096) · `top_p` (0–1) · `compare` (bool)
`image_b64` (base64 → forces vision) · `image_mime_type`
`file_ids` (list[str], default []) — explicit file UUIDs to attach per-request (canvas File→Session wire); merged with conversation-attached files in `helpers.py`; ownership-checked against `current_user.id` before use; triggers embedding + reasoning model (70B) same as conversation files

---

## AI Agent Tool Loop
- Trigger: any message when `file_ids` non-empty → always forces reasoning model (70B); 8B cannot reliably use tool results
- File tools always available when files attached (not keyword-gated); `_needs_file_tools()` no longer gates tool availability

- Tools (19 total — 11 existing + 7 canvas + 1 creation): `list_files` · `read_file` (100k cap, capped to 12000 chars in context) · `write_file` · `create_file` · `append_to_file` · `patch_file` (fuzzy) · `search_in_file` · `search_across_files` · `ask_user` · `query_graph` · `write_memory` · `create_canvas_node` · `delete_canvas_node` · `update_canvas_node` · `wire_nodes` · `unwire_nodes` · `query_canvas` · `get_canvas_graph` · `create_conversation` (Postgres Conversation + returns id; auto-creates+wires its session canvas node via `_ensure_creation_wiring` — AI must NOT create/wire it)
- Guards: same tool **with identical args** repeated → abort (signature = `(name, json.dumps(args, sort_keys))`). Write tools `_MAX_IDENTICAL_CALLS=3`; read-only tools (`get_canvas_graph` is parameterless so every call collides; `query_canvas`) get `_MAX_IDENTICAL_READS=8` so legit re-reads across a multi-step task don't false-trip. Distinct-arg calls (bulk `delete_canvas_node` over many node_ids) flow freely — only a true loop (same delete/create/query repeated) trips. Bounded overall by `MAX_TOOL_ITERATIONS=60` · tool result stored in context capped at 12000 chars (prevents 70B refusal on large repeated reads)
- **Canvas tool gating (J1, 2026-06-04):** ALL canvas tools (read + write) are withheld unless `canvas_context_active(message, conv_id)` (`executor.py`) is true — i.e. the message names a canvas object (`_CANVAS_INTENT_RE`: canvas/node/session/conversation/wire/graph…) OR a creation flow is mid-confirmation (Redis state set). Applied in `llm/service/stream.py` (`canvas_tools = []` when inactive). Without this the 70B treats every benign turn as a canvas task and loops on whatever tool is offered (gating only write tools just makes it spin on read-only). Tradeoff: canvas STATE/inventory still injected, so the model may narrate the canvas on benign turns — no loop.
- **Creation guard** (`create_conversation`): 3-layer state machine in `executor.py` (`_run_creation_guard`)
- `ask_user` / `write_memory` emit SSE + done → pauses loop; amber/green card in UI; `POST /api/memory/write` on user confirm; `ask_user` question persisted as assistant message content so model sees it on next turn
- `append_to_file` for explicit write requests only; `search_in_file` preferred over `read_file` for sections

---

## Agent Canvas Architecture

### Node Registry (`agent/node.py`)
- `Node` dataclass: `name`, `label`, `ports` (input/output), `tools`, `default_config`, + policy flags `embedded` / `ai_creatable` / `permanent`
- 11 node types: `input`, `session`, `memory`, `files`, `logs`, `usage`, `config`, `insights`, `goals`, `automations`, `mech`
- `registry: dict[str, Node]` and `get_node_type()` lookup
- **Single source of truth for type classification** (H1): derived frozensets — `EMBEDDED_TYPES` (insights/goals/automations/mech), `AI_CREATABLE_TYPES` (files/logs/usage), `PERMANENT_TYPES` (input/memory/config), `MANAGED_TYPES` (input/session/memory/config — internal-create only). Consumed by `canvas_graph.create_node`, `api/chat/stream.py` (`_CREATABLE_NODES`), `llm/tools/schemas.py`. Never re-hardcode these sets.
- **`create_node` guard:** rejects `EMBEDDED_TYPES`; rejects `MANAGED_TYPES` unless `internal=True` (bootstrap paths `_ensure_canvas_wiring` / `_ensure_creation_wiring`); rejects non-UUID `config.conversation_id`.
- **Session identity (H4):** `config.kind` = `"global"` (permanent JARVIS session, set by `_ensure_canvas_wiring`) vs `"user"` (ordinary, set by `_ensure_creation_wiring`); CANVAS STATE renders `[GLOBAL]` / `[user session]`.

### Canvas Graph CRUD (`agent/canvas_graph.py`)
- create/delete/update `CanvasNode` (label separate from `Entity`); wire/unwire with port validation; get_node with incident wires
- get_canvas_graph (Redis `canvas:{uid}` TTL 60s); read-only `query_canvas` (write keyword guard); scratchpad R/W via SQLAlchemy `UserMemory.agent_scratchpad` (append-only merge)
- All ops scoped to `CanvasNode` / `agent_scratchpad` / `canvas:` prefix — never touch `Entity`, `UserMemory.content`, or `graph:*` keys

## Creation Guard (`llm/tools/executor.py`)

3-layer state machine preventing `create_conversation` without explicit user intent.

### Layer 1 — Redis Flow State
- Key: `creation_flow:{conv_id}`, TTL 300s
- States: `pending_specs` → `confirmed`
- Set to `pending_specs` when Layer 2 detects creation intent
- Set to `confirmed` when Layer 3 confirms user reply matches `_CONFIRMATION_RE`
- Cleared on successful creation; degrades gracefully when Redis unavailable (falls through to Layer 2)
- `confirmed` → allow; `pending_specs` → run Layer 3. **No** latest-message cross-check on these states — it broke the confirm turn (the "yes" message has no creation intent of its own, so re-detecting `_CREATION_RE` cleared the flow and rejected). Stale-leak prevention is now handled upstream by canvas tool gating (`canvas_context_active`) + Layer 3's affirmative-reply requirement.

### Layer 2 — Latest Message Intent
- Queries ONLY the most recent user message (`.limit(1)`) — not last 3
- Matches against `_CREATION_RE`: `(create|new|make|start|set up|setup)...(session|conversation)` or reverse order
- Skips messages matching `_NEGATION_RE` (don't create, never mind, cancel, etc.)
- Also checks `noun in text` or generic `(create|new|make|start) (one|a|an|the|this|some)`
- Returns `ASK_USER_PREFIX` to ask user for specs + confirmation

### Layer 3 — Confirmation Check
- Runs when Redis state is `pending_specs`
- Scans last 4 messages for assistant ASK_USER content ("I need your confirmation") followed by user reply
- User reply must match `_CONFIRMATION_RE`: `yes|yeah|sure|confirm|create|do it|proceed|go ahead|make it|let's do|okay?|please|that sounds|agree|approved|start`
- Prevented false-positive: canvas queries like "what nodes are on my canvas?" do NOT match → stays pending

### Rejection Flow
- All 3 layers false → returns instructional rejection string (not `ASK_USER_PREFIX`): "Cannot create session: the user didn't request one."
- Model sees this as tool result text, can retry or move on
- If user hasn't confirmed → returns "The user hasn't confirmed yet. Wait for their response."

### Auto-wiring
- On successful creation, `_ensure_creation_wiring()` creates the matching session canvas node and wires it to the input node: `routed_message` → `message` (relation `routes_to`). The system prompt tells the model NOT to create/wire the node itself — auto-wiring owns it.

### Prompt Reinforcement (J1 anti-priming, 2026-06-04 — defense-in-depth only)
- NOTE: prompt changes alone did NOT fix J1 (the 70B looped regardless). The actual fix is canvas tool gating (see "Canvas tool gating" above). These prompt edits are kept as defense-in-depth.
- Node inventory RULES no longer name `create_conversation` (it primed the model to call it on benign turns). Single neutral rule: "You are in the JARVIS global session. Do not create sessions or nodes unless the user explicitly asks; answer normally otherwise."
- `create_conversation` tool description drops the old manual `create_canvas_node`/`wire_nodes` procedure (auto-wiring owns it) and says: "Only call when the user explicitly asks — never on greetings, topic suggestions, or general questions."
- Rejection messages now tell the model to STOP retrying: "Do not call this tool again. Answer the user's message normally instead." — breaks the reject→retry→loop-guard-abort cycle.

---

### Token Buffering (`llm/service/stream.py`)
- Tokens accumulated in `_token_buffer` per `call_stream` call
- If response contains tool calls → discard buffered tokens (prevent model from generating preamble text before tool execution, then duplicating it after)
- If no tool calls → flush buffer as normal SSE `content` events

---

### Boot Sequence (`agent/boot.py`)
- `agent_boot(user_id)` → `BootReport` with health, scratchpad, canvas graph, node_summary
- `_check_health()`: pings all models + embedding + Neo4j + Redis + Postgres in parallel
- `format_boot_log(report)`: formatted for system prompt injection

### System Prompt Injection (Step 7)
- Boot log, node inventory (11 types), and canvas state prepended to system message on every request
- Tier 0 (never dropped by context budget allocator)
- Combined size ~500 tokens
- Confirmation-protocol + session-creation instruction blocks REMOVED (they primed false creation framing). See Prompt Reinforcement above.
- No redundant "call get_canvas_graph for UUIDs" instruction — UUIDs already in `[CANVAS STATE]`
- Tool-calling instruction softened: "When tools are needed, call them" not "CRITICAL: call tools immediately"


---

## Memory System
Injection order: system → GRAPH CONTEXT → GRAPH FACTS → USER STATE → ACTIVE GOALS → PROJECT → RELEVANT CONTEXT → EARLIER IN THIS CONVERSATION → LAST SESSION → history → FILE CONTEXT → user message

- Triggers: memory update >3000 tok OR every 10 asst msgs; history compression + project summary update >4000 tok OR every 15 total msgs (all_count > 10); auto-title after 2nd msg via `asyncio.create_task`
- Lock: `pg_advisory_xact_lock(user_id)` prevents version races
- Compaction: LLM-driven dedup via `compact_memory()`; creates `UserMemoryVersion` snapshot; queued via ARQ or daily cron at 3 AM UTC; sets Redis lock `compact:running:{user_id}` (EX 300s) — graph extraction skips while held
- Preference extraction: `extract_preferences_job` every 50 asst msgs; writes `[PREFERENCES]` to `UserMemory.content`; Redis lock `pref_extract:running:{user_id}` EX 300s
- Behavior tracking: `update_behavior_profile_job` per reply; increments query_type/topic/tools/models counters in `UserBehaviorProfile.profile` JSONB; no LLM; feeds `generate_user_insight()`
- Context budget: drops lowest-tier sources when tokens exceed `context_window - max_output_tokens - 10%`; re-applied per tool iteration
- Salience: bumped on context load via `compute_salience()`, decayed 0.95/cycle during compaction; cleared when <0.3
- Conflict resolver: `MemoryConflict` stores fact_a/b/type/resolution/expires_at; +7d on scan; expired unresolved auto-resolved `keep_a`; resolve via `POST /memory/conflicts/{id}/resolve`
- Per-fact salience: `fact_saliences` JSONB maps fact→score; time-based decay `0.95^(hours/24)` before top-20; bumped per-access; <0.05 pruned; low-salience dropped first by budget allocator
- Retrieval re-ranking: `final_score * (1 + memory_salience * 0.05)` after retrieval

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
- Auth uses `bcrypt` directly (no passlib) — `hash_password()` + `verify_password()` in `auth/security.py`; existing `$2b$` hashes remain compatible
- Dotenv admin: `/admin/env` masks sensitive keys; PUT writes `.env` + updates running config; `POST /admin/env/reload` does `importlib.reload(config)`
- `.env` merge script in root CLAUDE.md — adds missing keys from `.env.example` as commented-out
- Debug mode: `retriever.retrieve()` / `retrieve_from_files(debug=True)` returns `(chunks, debug_info)` tuple; `/search?debug=true` returns `{"results": [...], "debug": [...]}`
- Eval harness: `tests/retrieval/test_hybrid_eval.py` — 26 tests, mock DB (AsyncMock), no NIM deps; run with `pytest tests/retrieval/ -v`
- Neo4j indexes created on startup: unique constraint `(user_id, name)`, fulltext `entity_name_ft` on `e.name`, range index `entity_user_id` on `e.user_id`, range index `canvas_user_id` on `CanvasNode.user_id`; writes use UNWIND batch (2 round-trips regardless of entity/rel count); graph query results cached in Redis (key `graph:{user_id}:{sha256[:32]}`, TTL 60s, USE_REDIS gated); cache busted on every entity write (`_cache_del_user`)
- NIM retry: `MAX_RETRIES=3` (4 total); exponential backoff with jitter `min(30, 2**attempt) * (0.75 + 0.5*random)` — attempt 0≈1s, 1≈2s, 2≈4s, 3≈8s
- Circuit breaker: _THRESHOLD=5, _COOLDOWN=90s; Redis-persisted `cb:open:{model}` EX 90; restored on startup via `restore_circuit_state()`; pre-tripped at startup by `probe_models_on_startup()` for any model returning non-200
- Prometheus: multiprocess mode active when `PROMETHEUS_MULTIPROC_DIR` set — `export_metrics()` uses `MultiProcessCollector(CollectorRegistry())`; new counters: `stream_interruptions_total`, `all_models_failed_total`, `arq_job_failed_total{job_type}`
- Summarizer imports: `api/chat/stream.py` imports `compress_history`, `update_memory`, `update_project_summary` from `llm.summarizer.*` — missing these causes `NameError` at runtime (caught by except handler, skips memory update)

---

## HANDOFF Protocol — Quick Reference

- **Role:** backend worker. Do not plan or delegate.
- **Scope:** `backend/` files only. Cross-dir tasks → put in `HANDOFF.md` section, pass file.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## backdir`, execute tasks, fill `### Recorded` (endpoint shapes, env vars, SSE events, DB columns), update this file, append History, `mv HANDOFF.md ../frontend/HANDOFF.md`.
- **Recorded facts:** write terse, precise — next agent has no backend context.

> Full protocol: `../HANDOFF_PROTOCOL.md`
