# HANDOFF
- Updated: 2026-05-30
- Status: active
- Owner: backend
- Archive: `HANDOFF_ARCHIVE.md`

---

## Active Feature: Knowledge Graph Explorer UI (ROADMAP #8)

### What
Replace the stats-only Graph tab in MemoryPanel with an interactive visual graph. Nodes = entities, edges = relations. Click a node to see linked facts and conversation references. Minor backend extension first, then heavy frontend canvas work.

### Backend tasks
- [ ] **Extend `GET /api/graph/sample`** — add query params `?limit=` (int, default 50, max 200) and `?entity_type=` (string, optional filter). Return existing shape unchanged; just respect the new params in the Cypher query.

### Files to touch (backend)
- `backend/api/graph.py` — update `/sample` route params + Cypher

### Pass instructions (backend → frontend)
When done: fill `### Recorded` below, set `status: needs-frontend`, `mv` to `../frontend/HANDOFF.md`.

### Recorded
_(backend worker fills this before passing)_

---

### Frontend tasks
_(filled by root after backend passes back)_

---

## History
| Date       | Feature                          | Notes |
|------------|----------------------------------|-------|
| 2026-05-30 | Fact-Level Salience Panel        | root → frontdir (done) |
| 2026-05-30 | Memory Conflict Resolution UI    | root → frontdir (done) |
| 2026-05-30 | Security & perf fixes            | frontdir (done) — role bug, stale closure, URL encode, useMemo |
| 2026-05-30 | Cross-Session Continuity Summary | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Behavioral Pattern Tracker       | root → backdir → done |
| 2026-05-30 | User Preference Extraction       | root → backdir → done |
| 2026-05-29 | Chat.jsx Refactor                | root → frontend → done |
| 2026-05-29 | Autonomous Memory Writing        | plan → backdir (done) → frontdir (done) |
| 2026-05-30 | Unified Search (ROADMAP #7)      | root → backdir (done) → frontdir (done) |
