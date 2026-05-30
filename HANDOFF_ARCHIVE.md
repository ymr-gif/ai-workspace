# HANDOFF ARCHIVE
Completed features — key design decisions and non-obvious implementation details.
Full code detail is in CLAUDE.md and git history.

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

## Pattern Detection + Proactive Triggers (ROADMAP #14)
**Completed:** 2026-05-31

- **`detect_recurring_patterns(profile)`** in `services/behavior.py` — reads `topic_keywords` JSONB; returns sorted list of topics with count ≥ 3; empty list = nothing to act on
- **Trigger in `arq_worker.py`** — after `update_behavior_profile_job`, calls detector; for each pattern checks dedup (`UserInsight` content ILIKE `%topic%` within 7 days); if clear, enqueues `generate_insight_job` with `hint="User frequently asks about: {topic}. Suggest creating a summary document."`
- **`generate_insight_job`** — added optional `hint` kwarg; passes to `generate_user_insight`
- **`agency.py:generate_user_insight`** — merged duplicate definition (second was silently overwriting first); added `hint` kwarg prepended to `behavior_hint` in prompt; `max_tokens=60`, `temperature=0.4`

**Key files:** `backend/services/behavior.py` · `backend/services/arq_worker.py` · `backend/llm/agency.py`

---

## Goal / Task Tracker (ROADMAP #13)
**Completed:** 2026-05-30

- **Model**: `UserGoal` in `models/user.py` — UUID PK, `user_id` FK, `title`, `description` (nullable), `status` (`active`/`completed`/`paused`, default `active`), `linked_conversation_ids` JSONB (default `[]`), `created_at`, `updated_at`; migration 035
- **CRUD**: `GET /goals` (`?status=` filter) · `POST /goals` · `PATCH /goals/{id}` · `DELETE /goals/{id}` (204) · `POST /goals/{id}/link/{conversation_id}`
- **Context injection**: `[ACTIVE GOALS]` block queried in `helpers.py:_build_stream_context`; formatted as numbered list; injected in `context.py` between `[USER STATE]` and `[WORKSPACE STATE]`; tier 3 budget (drops with workspace state under pressure); threaded through `stream.py` (both compare + main paths) and `llm/service/stream.py`
- **Frontend**: `GoalsPanel.jsx` slide-in (🎯 button in header); `useGoals.js` hook; create/edit inline overlay; status toggle (active↔paused); 🔗 Link conv button per active goal → `POST /goals/{id}/link/{conversation_id}`; ✓ Linked badge when already linked

**Key files:** `backend/models/user.py` · `backend/alembic/versions/035_user_goals.py` · `backend/api/goals.py` (new) · `backend/main.py` · `backend/llm/service/context.py` · `backend/api/chat/helpers.py` · `backend/api/chat/stream.py` · `backend/llm/service/stream.py` · `frontend/src/hooks/useGoals.js` (new) · `frontend/src/components/chat/GoalsPanel.jsx` (new) · `frontend/src/components/Chat.jsx`

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

