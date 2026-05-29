# HANDOFF
- Updated: 2026-05-30
- Status: active
- Owner: backend
- Archive: `HANDOFF_ARCHIVE.md`

---

## Active Feature: User Preference Extraction (ROADMAP #2 / P0)

Extract user preferences from conversation history via an ARQ background job. Writes a `[PREFERENCES]` section into `UserMemory.content`. Triggered every 50 assistant messages per user. No new migrations — uses existing `UserMemory` + `UserMemoryVersion`.

---

## backdir — User Preference Extraction

### Goal
After every 50 assistant messages from a user (counted across all conversations), enqueue an ARQ job that runs an LLM pass over recent history and writes extracted preferences (verbosity, tone, domains, response style) as a `[PREFERENCES]` section in `UserMemory.content`.

No new DB model. No migration. Uses existing lock + versioning patterns.

### Tasks
- [ ] Create `backend/llm/summarizer/preferences.py`
  - `extract_preferences(user_id: int, db: AsyncSession) -> None`
  - Fetch last 40 messages (user + assistant roles, any conversation, ordered `created_at DESC`) for the user via joined query on `messages` → `conversations.user_id`
  - Build prompt: extract `[PREFERENCES]` section with keys `verbosity`, `tone`, `domains`, `response_style` from the messages; ask for key: value format under `[PREFERENCES]` header
  - Call NIM reasoning model (70B), non-streaming — use existing `llm/nim.py` `call()` with `model=config.MODEL_REASONING`
  - Parse LLM response: find `[PREFERENCES]` block (lines between `[PREFERENCES]` and next `[` or EOF)
  - Acquire `pg_advisory_xact_lock(user_id)` in transaction
  - Load `UserMemory` for user (create if not exists, same pattern as `compact_memory`)
  - Replace existing `[PREFERENCES]` section in `content` if present; else append to end
  - Snapshot current content to `UserMemoryVersion` before write (same pattern as compact)
  - Bump `version += 1`, set `updated_at = now()`
  - Commit

- [ ] Add `extract_preferences_job` to `backend/services/arq_worker.py`
  - Signature: `async def extract_preferences_job(ctx, user_id: int)`
  - Get DB session via `async_session_factory()` (same as `compact_memory_job`)
  - Call `extract_preferences(user_id, db)`
  - `_MAX_TRIES = 4`, same error handling + `ARQ_JOB_FAILED` counter on final failure
  - Register in `WorkerSettings.functions` list

- [ ] Add trigger in `backend/api/chat/background.py`
  - In `run_background_tasks()`, after existing memory-write block
  - Query: `SELECT count(*) FROM messages m JOIN conversations c ON c.id = m.conversation_id WHERE c.user_id = :uid AND m.role = 'assistant'`
  - If `count > 0 and count % 50 == 0`:
    - Check Redis key `pref_extract:running:{user_id}` — skip if exists
    - SET `pref_extract:running:{user_id}` EX 300
    - Enqueue `extract_preferences_job(user_id)` via ARQ pool (inline fallback if pool unavailable: `asyncio.create_task`)
  - Gate entire block on `USE_REDIS` being true (same pattern as other Redis-gated features) — if Redis down, skip silently

- [ ] Update `backend/CLAUDE.md`
  - In Memory System section, add to the Compaction/ARQ block: `extract_preferences_job` — triggered every 50 assistant messages per user; writes `[PREFERENCES]` section to `UserMemory.content`; Redis lock `pref_extract:running:{user_id}` EX 300s

### Recorded
_(fill in after implementation — endpoint shapes, prompt used, any non-obvious decisions)_

---

## History
| Date       | Feature                       | Notes |
|------------|-------------------------------|-------|
| 2026-05-30 | User Preference Extraction    | root → backdir |
| 2026-05-29 | Chat.jsx Refactor             | root → frontend → done |
| 2026-05-29 | Autonomous Memory Writing     | plan → backdir (done) → frontdir (done) |
| 2026-05-28 | Adaptive Retrieval Policy     | root → backend → done |
| 2026-05-28 | Memory Salience Engine        | root → backend → done |
