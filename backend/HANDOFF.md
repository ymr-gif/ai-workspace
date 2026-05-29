# HANDOFF
- Updated: 2026-05-30
- Status: active
- Owner: backend
- Archive: `HANDOFF_ARCHIVE.md`

---

## Active Feature: Cross-Session Continuity Summary (ROADMAP #4 / P0)

On new conversation start, inject a `[LAST SESSION]` context block (last conv title + elapsed time). Tier 8 — drops first from context budget. Expose `last_session` in the `done` SSE event so the frontend can show a "Welcome back" banner (frontend is a separate pass).

---

## backdir — Cross-Session Continuity Summary

### Goal
When a user starts a NEW conversation (no `req.conversation_id`), query their most recent prior conversation, format a one-line summary (`Last session: "<title>" — X ago`), inject it as `[LAST SESSION]` in the context, and emit it in the `done` SSE event. No LLM, no migration, no new model — DB query + string formatting only.

### Tasks

- [ ] **`backend/api/chat/helpers.py`** — add last-session query to `_build_stream_context()`
  - Only when `not req.conversation_id` (new conversation — `candidates` will be empty)
  - After the `conflicted_facts` block and before the `graph_context` block (~line 251), add:
    ```python
    last_session = ""
    if not req.conversation_id:
        ls_result = await db.execute(
            select(Conversation.title, Conversation.updated_at)
            .where(Conversation.user_id == current_user.id, Conversation.id != conv.id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        ls_row = ls_result.first()
        if ls_row and ls_row.title:
            elapsed = datetime.now(timezone.utc) - ls_row.updated_at
            hours = elapsed.total_seconds() / 3600
            if hours < 1:
                ago = f"{max(1, int(elapsed.total_seconds() / 60))} minutes ago"
            elif hours < 24:
                ago = f"{int(hours)} hours ago"
            else:
                ago = f"{int(hours / 24)} days ago"
            last_session = f'Last session: "{ls_row.title}" — {ago}'
    ```
  - `Conversation` and `select` are already imported; `datetime`/`timezone` already imported
  - Add `"last_session": last_session` to the return dict (alongside `"policy_used"`, `"fact_saliences"`, etc.)

- [ ] **`backend/llm/service/context.py`** — wire `[LAST SESSION]` into context building
  - Add tier 8 to `_TIER_PREFIXES` list — insert BEFORE the existing tier 7 entry (highest tier = drops first):
    ```python
    (8, re.compile(r'^\[LAST SESSION\]')),                            # drop first
    (7, re.compile(r'^\[FILE CONTEXT\]')),                            # drop second
    ```
  - Add `last_session: str = ""` parameter to `build_context_messages()` signature (keyword-only after `conflicted_facts`)
  - Inject the block inside the `if memory_enabled:` guard, right after the system-prompt block and before `[GRAPH CONTEXT]` — as the first optional context block:
    ```python
    if last_session:
        messages.append({"role": "user",      "content": f"[LAST SESSION]\n{last_session}"})
        messages.append({"role": "assistant", "content": "Understood."})
    ```

- [ ] **`backend/api/chat/stream.py`** — pass `last_session` through
  - In the `build_context_messages(...)` call (~line 138–145): add `last_session=ctx.get("last_session", "")` as a keyword arg
  - In the `done` event handler (~line 207–315), where other ctx fields are already added to the event (e.g. `event["query_type"] = ctx.get("policy_used", "")`): add `event["last_session"] = ctx.get("last_session", "")`

- [ ] **`backend/CLAUDE.md`** — document
  - In the Memory System injection order list, add entry: `[LAST SESSION]` — tier 8 (drops first); new-conversation only; content = last conv title + elapsed time; emitted in `done` SSE event as `last_session`

### Recorded
_(fill in after implementation)_

---

## frontdir — Cross-Session Continuity Summary

### Goal
Show a dismissible "Welcome back" banner above the first AI message when `done.last_session` is non-empty. Banner should be subtle — not a card, just a small line above the first bubble.

### Tasks

- [ ] In `Chat.jsx` (or relevant hook): capture `last_session` from the `done` SSE event — state `lastSession` (string | null), set when a new conversation's first reply arrives
- [ ] Render the banner above the first assistant message in `MessageList.jsx`: small text line, muted colour (`#475569`), `✦ Last session: "…" — X ago`, auto-dismiss after 8 seconds or on user send
- [ ] Clear `lastSession` on next user send (alongside `setProactive(null)`)

### Recorded
_(fill in after implementation)_

---

## History
| Date       | Feature                       | Notes |
|------------|-------------------------------|-------|
| 2026-05-30 | Behavioral Pattern Tracker    | root → backdir → done |
| 2026-05-30 | User Preference Extraction    | root → backdir → done |
| 2026-05-29 | Chat.jsx Refactor             | root → frontend → done |
| 2026-05-29 | Autonomous Memory Writing     | plan → backdir (done) → frontdir (done) |
| 2026-05-28 | Adaptive Retrieval Policy     | root → backend → done |
