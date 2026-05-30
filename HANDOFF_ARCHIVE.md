# HANDOFF ARCHIVE
Completed features — key design decisions and non-obvious implementation details.
Full code detail is in CLAUDE.md and git history.

---

## Autonomous Memory Writing
**Completed:** 2026-05-29

- **Tool**: `write_memory(fact: str)` — always available when `memory_enabled=True`
- **Flow**: tool call → executor returns `__CONFIRM_WRITE_MEMORY__:{fact}` sentinel → stream yields `{type:"confirm_write_memory", fact}` + `{type:"done"}` → generator returns (stream pauses, like ask_user)
- **API**: `POST /memory/write` — appends fact as new line (trim 500 chars), snapshots to `UserMemoryVersion`, bumps `version +1`, boosts `salience +0.1`
- **Frontend**: `pendingWriteFact` in `useConversations`; green card (bg `rgba(52,211,153,0.08)`, border `rgba(52,211,153,0.25)`); cleared on Accept (calls API), Dismiss, or next send

**Key files:** `llm/tools/schemas.py` · `llm/tools/executor.py` · `llm/service/stream.py` · `api/memory.py` · `hooks/useConversations.js` · `chat/MessageList.jsx`

---

## Memory Conflict Resolver
**Completed:** 2026-05-28

- **Model**: `MemoryConflict` — `id` (UUID PK), `user_id` FK, `fact_a`, `fact_b`, `conflict_type` (contradiction|duplicate|ambiguous), `resolution` (keep_a|keep_b|merge|discard_both|unresolved)
- **Detection**: pairwise LLM (llama) check post-compaction; skips `"none"` pairs
- **Suppression**: unresolved conflicts filtered from `[USER STATE]` injection at context build time
- **Resolution**: `POST /memory/conflicts/{id}/resolve` applies patch to `UserMemory.content`, bumps version
- **Migration**: 028

**Key files:** `models/user.py` · `alembic/028_memory_conflicts.py` · `llm/summarizer/conflicts.py` · `llm/service/context.py` · `api/memory.py`

---

## Adaptive Retrieval Policy
**Completed:** 2026-05-28

- **Classifier**: `classify_query(msg)` in `router.py` → `factual|relational|temporal|broad`; keyword-set matching, fallback `factual`
- **Policy map** in `retriever/policy.py`:
  - `factual` → weighted, alpha=0.7, top_k=5
  - `relational` → RRF, top_k=8, use_graph=true
  - `temporal` → RRF, k_sparse=10, top_k=6
  - `broad` → weighted, alpha=0.3, top_k=3
- Applied per-request in `_build_stream_context()`; logged with query_type + params

**Key files:** `llm/router.py` · `llm/retriever/policy.py` · `api/chat/helpers.py`

---

## Salience Integration Completion
**Completed:** 2026-05-28

- **Per-fact salience**: `UserMemory.fact_saliences` JSONB maps fact text → score (default 1.0)
- **Injection**: facts sorted high→low before `[USER STATE]` (top 20); bumped per-access via `bump_fact_saliences()`
- **Budget**: tier-1 partial drop removes low-salience facts (< 0.5) before dropping entire `[USER STATE]` block
- **Decay**: per compaction cycle; facts < 0.3 dropped from saliences map
- **Retrieval re-rank**: `final_score * (1 + memory_salience * 0.05)`
- **Migration**: 029

**Key files:** `models/user.py` · `llm/summarizer/salience.py` · `api/chat/helpers.py` · `llm/service/context.py`

---

## Memory Salience Engine
**Completed:** 2026-05-28

- **Fields on `UserMemory`**: `salience` (float, default 1.0), `confidence` (float, default 1.0), `last_used_at`
- **`compute_salience()`**: recency decay (exponential 0.05) + frequency cap (+10%/access), clamped [0,2]
- **Compaction**: decays ×0.95/cycle; clears memory entirely if salience < 0.3
- **Read-time**: bumped on every context load; `POST /memory/decay` for manual pass
- **Migration**: 027

**Key files:** `models/user.py` · `llm/summarizer/salience.py` · `llm/summarizer/compact.py` · `api/memory.py`

---

## Memory Compaction Job
**Completed:** 2026-05-28

- **`compact_memory()`**: `pg_advisory_xact_lock(user_id)` → skips if < 100 words → LLM (llama) dedup/compress → cap 500 words → snapshot to `UserMemoryVersion`
- **ARQ job**: `compact_memory_job` — queued via pool; `max_tries=4`
- **Cron**: daily 3 AM UTC via APScheduler in `scheduler_worker.py`
- **API**: `POST /memory/compact` → enqueues ARQ job

**Key files:** `llm/summarizer/compact.py` · `services/arq_worker.py` · `services/scheduler_worker.py` · `api/memory.py`

---

## Cross-Session Continuity Summary
**Completed:** 2026-05-30

- **Backend** (`helpers.py`): `_build_stream_context()` — when `not req.conversation_id`, queries last prior conv `title + updated_at`, formats elapsed time (minutes/hours/days); stored in `ctx["last_session"]`
- **Context injection** (`context.py`): `[LAST SESSION]` tier-8 block (drops first from budget); `build_context_messages()` `last_session` kwarg; injected inside `memory_enabled` guard before `[GRAPH CONTEXT]`; `_TIER_PREFIXES` entry `(8, [LAST SESSION])` before `(7, [FILE CONTEXT])`
- **Stream wiring** (`stream.py`): passed through compare + main flows; emitted in `done` SSE event as `"last_session"`
- **Frontend** (`useConversations.js`): `lastSession` state; set from `done.last_session`; cleared on send; `setTimeout(8000)` auto-dismiss
- **Banner** (`MessageList.jsx`): `✦ {lastSession}` above first AI bubble; `fontSize: "0.72rem"`, `color: "#475569"`, no border/background
- **No LLM, no migration, no new model**

**Key files:** `api/chat/helpers.py` · `llm/service/context.py` · `llm/service/stream.py` · `api/chat/stream.py` · `hooks/useConversations.js` · `components/chat/MessageList.jsx`

---

## Security & Perf Fixes (Frontend)
**Completed:** 2026-05-30

- **Role bug**: AI messages use `role: 'ai'` (not `'assistant'`) — `MessageList.jsx` conditions updated to match
- **Stale closure**: `deleteInsight` in `InsightsPanel` now captures `wasUnread` before the `await` to avoid reading stale state
- **URL encode**: `conversation_id` query param in `useToolLogs.js` wrapped in `encodeURIComponent`
- **useMemo**: `attachedIds` in `useFiles.js` converted from inline `new Set()` to `useMemo`; derived memory values in `Chat.jsx` (`sections`, `projectSections`, `hasMemory`, `wordCount`, `diffTarget`, `diffLines`) confirmed as `useMemo`

**Key files:** `components/chat/MessageList.jsx` · `components/chat/InsightsPanel.jsx` · `hooks/useToolLogs.js` · `hooks/useFiles.js` · `components/Chat.jsx`

---

## User-Defined Scheduled Agents (ROADMAP #12)
**Completed:** 2026-05-30

- **Backend audit**: `ScheduledPrompt` CRUD already existed in `api/scheduled_prompts.py` (233 lines); router registered at `/scheduled-prompts` in `main.py`
- **Backend additions**: `_SCHEDULE_ALIASES` (`daily/weekly/monthly` → cron); `_resolve_schedule()` helper; `croniter` validation; `workspace_id` column (UUID FK, migration 034) added to model + schemas + `_schedule_row()`
- **Frontend**: `useScheduledPrompts.js` hook (`loadPrompts`, `createPrompt`, `updatePrompt`, `deletePrompt`, `triggerRun`); `AutomationsPanel.jsx` slide-in (⏱ button in header); card list with schedule badge + active toggle; create/edit inline overlay (name, prompt, schedule pills, workspace selector, model override); 🗑 delete per card; expandable run history with ▶ manual trigger

**Key files:** `backend/models/prompts_scheduled.py` · `backend/alembic/versions/034_scheduled_prompt_workspace.py` · `backend/api/scheduled_prompts.py` · `frontend/src/hooks/useScheduledPrompts.js` (new) · `frontend/src/components/chat/AutomationsPanel.jsx` (new) · `frontend/src/components/Chat.jsx`

---

## Scheduled Backup (ROADMAP #11)
**Completed:** 2026-05-30

- **`config.py`**: `BACKUP_SCHEDULE = os.getenv("BACKUP_SCHEDULE", "0 2 * * *")`
- **`scheduler_worker.py`**: `run_backup()` async function; resolves `docker/backup.sh` via `Path(__file__).resolve().parent.parent.parent / "docker" / "backup.sh"`; runs via `asyncio.create_subprocess_exec("bash", ...)`; logs stdout (truncated 300 chars) + stderr on failure; registered with `CronTrigger.from_crontab(BACKUP_SCHEDULE)`
- **`.env.example`**: `BACKUP_SCHEDULE=0 2 * * *` added under Scheduled Backup section

**Key files:** `backend/config.py` · `backend/services/scheduler_worker.py` · `.env.example`

---

## Full Data Export (ROADMAP #10)
**Completed:** 2026-05-30

- **Endpoint**: `GET /api/export/full` in `backend/api/export.py`; `StreamingResponse(application/zip)` with `Content-Disposition: attachment; filename=export.zip`
- **ZIP contents**: `conversations/<uuid>_<title>.md` (role+content markdown) · `files/<filename>` (raw bytes from `storage_path`, missing skipped) · `memory/sheet.txt` · `memory/versions/<version>.txt` · `graph/entities.json` (top 500 entities, skipped if Neo4j unavailable)
- **Graceful degradation**: each section wrapped independently; empty data = ZIP with directories only
- **Frontend**: "⬇ Export All Data" button at bottom of `UsagePanel.jsx`; fetch → blob → `URL.createObjectURL` → `<a download="export.zip">`; `exporting` loading state disables button during fetch; token from `localStorage.getItem("nim_token")`

**Key files:** `backend/api/export.py` (new) · `backend/main.py` · `frontend/src/components/chat/UsagePanel.jsx`

---

## Knowledge Graph Explorer UI (ROADMAP #8)
**Completed:** 2026-05-30

- **Backend**: `GET /api/graph/sample?limit=&entity_type=` — `limit` int default 50 clamped 1–200; `entity_type` optional string filter on source node `.type`; dynamic WHERE clause in Cypher; shape unchanged (`{available, triples[{source, relation, target}]}`)
- **Frontend**: SVG circle-layout graph in Memory → Graph tab; nodes as circles, edges as lines; click node → highlights edges + neighbors + shows relation list below; controls: entity_type text filter + limit input + refresh button; stats count cards kept above graph
- **State**: `graphSample` / `graphSampleLoading` / `loadGraphSample` in `useInsights.js`; loads on tab click alongside existing stats

**Key files:** `backend/api/graph.py` · `frontend/src/components/chat/MemoryPanel.jsx` · `frontend/src/hooks/useInsights.js`

---

## Unified Search (ROADMAP #7)
**Completed:** 2026-05-30

- **Endpoint**: `GET /api/search?q=&scope=all|files|conversations|memory|graph` in `backend/api/search.py`; registered at `/api/search` in `main.py`
- **Fan-out**: `asyncio.gather` across all 4 stores when `scope=all`; graceful degradation — each store wrapped in try/except, failures return `[]`
- `files`: vector cosine sim on `FileChunk.embedding`; embedding fetched first
- `conversations`: `content_tsv @@ websearch_to_tsquery`; GIN index; scored via `ts_rank`
- `memory`: case-insensitive substring match on `UserMemory.content` lines; score from `fact_saliences` or 1.0
- `graph`: Neo4j `entity_name_ft` fulltext index; returns name, type, relation_count; empty when driver unavailable
- **Response**: `{query, scope, results[{source, score, title, snippet, id}]}` sorted descending; top 5 per store
- **Frontend**: `SearchPanel.jsx` slide-in (🔍 button in header); `useSearch.js` hook; 300ms debounce; scope filter pills (All/Files/Conversations/Memory/Graph); results grouped by source with colored labels; conversation click calls `selectConv(id)`

**Key files:** `backend/api/search.py` (new) · `backend/main.py` · `frontend/src/components/chat/SearchPanel.jsx` (new) · `frontend/src/hooks/useSearch.js` (new) · `frontend/src/components/Chat.jsx`

---

## Fact-Level Salience Panel
**Completed:** 2026-05-30

- **Score bar**: replaced `<span>` text badge with a narrow horizontal bar (`height: 4px`, `border-radius: 2px`); width = `salience * 100%`; color green (`#34d399`) ≥ 0.7, amber (`#fbbf24`) ≥ 0.4, grey (`#475569`) below; `%` label as small text to the right
- **Last-access timestamp**: muted line below each fact card — `Last accessed: X ago` (relative minutes/hours/days); `Never accessed` when `last_used_at` is null; `font-size: 0.65rem`, `color: #475569`
- **Data source**: `facts[].last_used_at` (ISO or null) already returned by `GET /api/memory` — no backend changes

**Key files:** `frontend/src/components/chat/MemoryPanel.jsx`

---

## Memory Conflict Resolution UI
**Completed:** 2026-05-30

- **Tab**: Conflicts tab added to `MemoryPanel.jsx` (after Graph); label shows count badge when > 0
- **Load**: `GET /api/memory/conflicts` on tab open; `conflicts` / `conflictsLoading` / `loadConflicts` / `resolveConflict` state in `useMemory.js`
- **Card**: `fact_a` + `fact_b` side by side; type badge red=contradiction / yellow=duplicate / grey=ambiguous
- **Resolve**: Keep A / Keep B / Merge / Discard Both → `POST /api/memory/conflicts/{id}/resolve` `{ strategy }` → card removed on success
- **Empty state**: "No conflicts" placeholder
- **Backend**: no changes — `GET /memory/conflicts` + `POST /memory/conflicts/{id}/resolve` were already complete

**Key files:** `frontend/src/components/chat/MemoryPanel.jsx` · `frontend/src/hooks/useMemory.js`

---

## Behavioral Pattern Tracker
**Completed:** 2026-05-30

- **Model**: `UserBehaviorProfile` in `models/user.py` — `user_id` PK, `profile` JSONB (`query_types / topic_keywords / tools_used / models_used / total_messages`), `updated_at`; migration 033
- **Core logic**: `services/behavior.py` — `update_behavior_profile()` — no LLM; stopwords + len>4 keyword extraction; topic pruning at 50 keys
- **ARQ job**: `update_behavior_profile_job` — `_MAX_TRIES=4`, `ARQ_JOB_FAILED` counter; registered in `WorkerSettings.functions`; enqueued every reply from `stream.py` done handler; no inline fallback
- **Insight enhancement**: `llm/agency.py` — `generate_user_insight()` accepts optional `behavior_profile` kwarg; top 3 query types + top 5 topics appended as `{behavior_hint}` in `_INSIGHT_PROMPT`; `generate_insight_job` loads `UserBehaviorProfile` and passes it

**Key files:** `models/user.py` · `alembic/versions/033_user_behavior_profile.py` · `services/behavior.py` · `services/arq_worker.py` · `api/chat/stream.py` · `llm/agency.py`

---

## User Preference Extraction
**Completed:** 2026-05-30

- **New file**: `llm/summarizer/preferences.py` — `extract_preferences(user_id, db)`
- **Prompt**: `_PREF_SYSTEM` — asks for `[PREFERENCES]` block with keys `verbosity`, `tone`, `domains`, `response_style`
- **LLM**: `MODELS["reasoning"]` (70B), non-streaming via `nim.call()`
- **Message fetch**: last 40 messages (user+assistant), joined `messages→conversations.user_id`, ordered `created_at DESC`
- **Parsing**: regex `\[PREFERENCES\](.*?)(?=\[|$)` — block between `[PREFERENCES]` and next `[` or EOF
- **Write**: `pg_advisory_xact_lock(user_id)`, snapshot to `UserMemoryVersion`, replace existing `[PREFERENCES]` or append, bump `version += 1`
- **ARQ job**: `extract_preferences_job` in `services/arq_worker.py`, `_MAX_TRIES=4`, `ARQ_JOB_FAILED` counter on final failure
- **Trigger**: `api/chat/stream.py` `event_generator()` — counts `asst_count`, fires at `% 50 == 0`, Redis lock `pref_extract:running:{user_id}` EX 300s, gated on `USE_REDIS`, inline fallback via `asyncio.create_task`
- **No new DB models or migrations**

**Key files:** `llm/summarizer/preferences.py` · `services/arq_worker.py` · `api/chat/stream.py` · `backend/CLAUDE.md`

---

## Retrieval Eval Harness + Neo4j Grounding Injection
**Completed:** 2026-05-28

- **Eval harness**: `tests/retrieval/test_hybrid_eval.py` — 26 tests, mock DB (AsyncMock), no NIM deps; 4 adaptive policy types tested; `pytest tests/retrieval/ -v`
- **Neo4j grounding**: `[GRAPH CONTEXT]` + `[GRAPH FACTS]` blocks in context injection; both backed by Redis cache (60s TTL); `query_graph` tool in agent loop

**Key files:** `tests/retrieval/test_hybrid_eval.py` · `tests/retrieval/conftest.py` · `llm/graph_memory.py` · `llm/service/context.py`

---

## Re-embed on MODEL_EMBEDDING Change + Graph Memory
**Completed:** 2026-05-28

- **Re-embed**: startup compares `MODEL_EMBEDDING` env vs `system_config` DB row; queues ARQ batches of 100 on mismatch; `POST /admin/re-embed` for manual trigger
- **Neo4j**: async driver; fails open if `NEO4J_PASSWORD` unset; constraint `(user_id, name)` unique + fulltext index `entity_name_ft` + range index `entity_user_id` created at startup
- **Graph writes**: `extract_and_store()` fires post-reply; UNWIND batch (2 round-trips); entity + relation per user
- **Graph context**: `[GRAPH CONTEXT]` injected when memory enabled; `[GRAPH FACTS]` from `query_by_keywords()`; both cached in Redis 60s
- **`query_graph` tool**: available in agent loop
- **Migration**: 026 (`system_config` table)
- **Env vars**: `NEO4J_URI` (bolt://neo4j:7687) · `NEO4J_USER` (neo4j) · `NEO4J_PASSWORD` (required to enable)
- **Driver**: `max_connection_pool_size=20`, `connection_timeout=5s`

**Key files:** `core/neo4j_client.py` · `llm/graph_memory.py` · `services/re_embed.py` · `api/graph.py` · `alembic/026_system_config.py`
