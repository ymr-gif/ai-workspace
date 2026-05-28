# HANDOFF
- Updated: 2026-05-29
- Status: idle
- Owner: root
- Archive: `HANDOFF_ARCHIVE.md`

---

## Active Feature: —

_(no active feature)

---

---
## backdir — Autonomous Memory Writing

### Goal
AI proposes memory writes mid-conversation via new `write_memory` tool. On trigger, yields a green confirmation card (like `ask_user` but green). On confirm, frontend calls API to append fact to `UserMemory.content`.

No new DB columns. No migrations.

### Tasks
- [x] Add `WRITE_MEMORY_SCHEMA` in `backend/llm/tools/schemas.py`
- [x] Add `CONFIRM_WRITE_PREFIX` + handler in `backend/llm/tools/executor.py`
- [x] Export both from `backend/llm/tools/__init__.py`
- [x] Update `backend/llm/service/stream.py` — tool availability + CONFIRM_WRITE_PREFIX handling
- [x] Add `POST /api/memory/write` in `backend/api/memory.py`
- [x] Append docs to `backend/CLAUDE.md`

### Recorded
- **Tool schema**: `write_memory(fact: str)` — agent requests memory write; user must confirm
- **SSE event**: `{type:"confirm_write_memory", fact:"..."}` — forwarded by event_generator, same as ask_user
- **API**: `POST /api/memory/write` — body `{fact: str}`, reads existing content, appends fact as new line, snapshots version, bumps version +1, boosts salience +0.1
- **Tool availability**: always when `memory_enabled=True`, regardless of file attachments
- **Flow**: tool call → executor returns `__CONFIRM_WRITE_MEMORY__:{fact}` → stream yields `{type:"confirm_write_memory", fact}` + `{type:"done"}` → generator returns (stream ends)

---
## frontdir — Autonomous Memory Writing

### Tasks
- [x] Add `pendingWriteFact` state in `Chat.jsx` (`useState(null)`)
- [x] Add SSE handler for `confirm_write_memory` event → `setPendingWriteFact(event.fact)`
- [x] Render green confirmation card below AI message when `pendingWriteFact` truthy
  - Green theme: bg `rgba(52,211,153,0.08)`, border `rgba(52,211,153,0.25)`, label `#34d399`, fact text `#6ee7b7`
  - Icon: `✓` (checkmark, `#34d399`)
  - Label: "MEMORY SUGGESTION"
  - Accept button: `#34d399` bg, `#0f172a` text, `cursor:pointer`
  - Dismiss button: ghost style, `border:1px solid #334155`, `color:#94a3b8`
- [x] Accept handler → `POST /api/memory/write {fact: pendingWriteFact}` with auth headers → on 200: `setPendingWriteFact(null)`
- [x] Dismiss handler → `setPendingWriteFact(null)`
- [x] Clear `pendingWriteFact` on next user message send (in `send()`)

### Recorded
- **State variable**: `pendingWriteFact` added to `useConversations` hook
- **SSE event consumed**: `confirm_write_memory` in Chat.jsx `send()` handler
- **Card renders**: below message feed, above proactive suggestion card; same positioning style as ask_user
- **Accept calls**: `POST /api/memory/write {fact}` with `Authorization: Bearer` header
- **Clear on send**: `setPendingWriteFact(null)` in send() alongside `setProactive(null)`

---
## History
| Date       | Feature                       | Notes |
|------------|-------------------------------|-------|
| 2026-05-29 | Chat.jsx Refactor             | root → frontend → done |
| 2026-05-29 | Autonomous Memory Writing     | plan → backdir (done) → frontdir (done) |
| 2026-05-28 | Adaptive Retrieval Policy     | root → backend → done |
| 2026-05-28 | Memory Salience Engine        | root → backend → done |
| 2026-05-28 | Retrieval Eval Harness        | root → backend → done |
| 2026-05-28 | Neo4j Grounding Injection     | root → backend → done |
