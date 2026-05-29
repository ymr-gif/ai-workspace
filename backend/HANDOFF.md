# HANDOFF
- Updated: 2026-05-30
- Status: active
- Owner: backend
- Archive: `HANDOFF_ARCHIVE.md`

---

## Active Feature: Behavioral Pattern Tracker (ROADMAP #3 / P0)

Track topics, query types, and tools engaged per user. Store as `UserBehaviorProfile` with a JSONB `profile` column (one row per user). Updated in background post-reply — no LLM, just counter increments. Feeds `generate_user_insight()` in `agency.py` with richer behavioral context.

---

## backdir — Behavioral Pattern Tracker

### Goal
After every assistant reply, fire a lightweight async task that increments per-user counters (query type, topic keywords, tools used, model used) in a new `user_behavior_profiles` table. The existing `generate_insight_job` in `arq_worker.py` is enhanced to load this profile and pass it to `generate_user_insight()` so insights become behavior-aware.

Uses a dedicated ARQ job — same pattern as `compact_memory_job` / `extract_preferences_job`. `asyncio.create_task` was rejected: missed increments are unrecoverable (no re-embed equivalent), and ARQ gives retry + `ARQ_JOB_FAILED` observability for free. New migration 033.

### Tasks

- [ ] Add `UserBehaviorProfile` to `backend/models/user.py`
  ```python
  class UserBehaviorProfile(Base):
      __tablename__ = "user_behavior_profiles"
      user_id:    Mapped[int]      = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
      profile:    Mapped[dict]     = mapped_column(JSONB, nullable=False, default=dict)
      updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
  ```
  Profile JSONB shape:
  ```json
  {
    "query_types":    {"factual": 12, "relational": 5, "temporal": 3, "broad": 2},
    "topic_keywords": {"docker": 5, "memory": 10, "python": 8},
    "tools_used":     {"read_file": 3, "write_memory": 1},
    "models_used":    {"llama": 20, "coder": 8, "reasoning": 5},
    "total_messages": 33
  }
  ```

- [ ] Export `UserBehaviorProfile` from `backend/models/__init__.py`
  - Add to import line from `.user` and to `__all__`

- [ ] Create `backend/alembic/versions/033_user_behavior_profile.py`
  - `upgrade()`: `op.create_table("user_behavior_profiles", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True), sa.Column("profile", postgresql.JSONB(), nullable=False, server_default="{}"), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))`
  - `downgrade()`: `op.drop_table("user_behavior_profiles")`
  - Set `down_revision` to `"032"`, `revision` to `"033"`

- [ ] Create `backend/services/behavior.py`
  - `_STOP_WORDS` set: common English words to exclude from topic extraction (`{"about", "after", "also", "been", "before", "being", "between", "could", "does", "doing", "during", "each", "from", "have", "having", "here", "into", "just", "like", "make", "more", "other", "should", "some", "that", "their", "them", "then", "there", "these", "they", "this", "those", "through", "very", "want", "what", "when", "where", "which", "while", "will", "with", "would", "your"}`)
  - `_MAX_TOPICS = 50`
  - `async def update_behavior_profile(user_id: int, query_type: str, message: str, tool_names: list[str], model_used: str, db: AsyncSession) -> None`:
    1. `row = await db.get(UserBehaviorProfile, user_id)` — if None, create and `db.add(row)`
    2. `profile = dict(row.profile)` — copy
    3. Increment `profile["query_types"][query_type]` (setdefault `{}`, get+1)
    4. Topic keywords: split `message`, lowercase, strip punctuation, keep words `len > 4` and not in `_STOP_WORDS`, take first 10; increment each in `profile["topic_keywords"]`; if `len > _MAX_TOPICS`, prune to top 50 by count
    5. Increment each tool name in `profile["tools_used"]`
    6. Increment `model_used` in `profile["models_used"]`
    7. `profile["total_messages"] = profile.get("total_messages", 0) + 1`
    8. `row.profile = profile`; `row.updated_at = datetime.utcnow()`; `await db.commit()`

- [ ] Add `update_behavior_profile_job` to `backend/services/arq_worker.py`
  - Signature: `async def update_behavior_profile_job(ctx, user_id: int, query_type: str, message: str, tool_names: list[str], model_used: str) -> None`
  - Get DB session via `AsyncSessionLocal()` (same pattern as other jobs)
  - Call `update_behavior_profile(user_id, query_type, message, tool_names, model_used, db)`
  - `_MAX_TRIES = 4`; `ARQ_JOB_FAILED.labels(job_type="update_behavior_profile").inc()` on final failure
  - Register in `WorkerSettings.functions`

- [ ] Trigger in `backend/api/chat/stream.py` `event_generator()`
  - Add `tools_in_turn: list[str] = []` near top of generator (alongside `model_used = "unknown"` at line 176)
  - In the event loop, when `event["type"] == "tool_call"`, append `event.get("name", "")` to `tools_in_turn` (line ~201 block)
  - After the `asst_count` / `pref_extract` block (~line 260), enqueue via ARQ pool:
    ```python
    if pool:
        await pool.enqueue_job(
            "update_behavior_profile_job",
            current_user.id,
            ctx.get("policy_used", "factual"),
            req.message,
            tools_in_turn,
            model_used,
        )
    ```
  - No inline fallback needed — a missed behavior increment is not critical enough to warrant spawning a raw coroutine on pool failure

- [ ] Enhance `backend/llm/agency.py` `generate_user_insight()`
  - Add `behavior_profile: dict | None = None` param (keyword-only, default None)
  - If provided and non-empty, append to prompt: top 3 query types by count + top 5 topic keywords by count, formatted as plain text
  - Update `_INSIGHT_PROMPT` to include an optional `{behavior_hint}` section (empty string when not provided)

- [ ] Enhance `generate_insight_job` in `backend/services/arq_worker.py`
  - After fetching `memory` + `recent_topics`, add:
    ```python
    from models import UserBehaviorProfile
    bp_row = await db.get(UserBehaviorProfile, user_id)
    behavior_profile = bp_row.profile if bp_row else {}
    ```
  - Pass `behavior_profile=behavior_profile` to `generate_user_insight(...)`

- [ ] Update `backend/CLAUDE.md`
  - Add `UserBehaviorProfile` to Key Models section: one row per user, JSONB `profile` with `query_types / topic_keywords / tools_used / models_used / total_messages`; updated via ARQ `update_behavior_profile_job` post-reply; feeds `generate_user_insight()`; migration 033
  - Note `update_behavior_profile_job` in the ARQ jobs section alongside `extract_preferences_job`

### Recorded
_(fill in after implementation)_

---

## History
| Date       | Feature                       | Notes |
|------------|-------------------------------|-------|
| 2026-05-30 | Behavioral Pattern Tracker    | root → backdir |
| 2026-05-30 | User Preference Extraction    | root → backdir → done |
| 2026-05-29 | Chat.jsx Refactor             | root → frontend → done |
| 2026-05-29 | Autonomous Memory Writing     | plan → backdir (done) → frontdir (done) |
| 2026-05-28 | Adaptive Retrieval Policy     | root → backend → done |
