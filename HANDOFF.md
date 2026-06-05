# HANDOFF
- Updated: 2026-06-05
- Status: done
- Owner: root (implemented under explicit override — user granted full permission to bypass "root does not implement")
- Archive: `HANDOFF_ARCHIVE.md`

---

## Active Feature: Canvas tool robustness — J2 (A+B+C+D) — ✅ DONE (shipped, verified live, see BUGS.md J2)

**Context.** Live test (global JARVIS, 2026-06-05 ~05:01) aborted: model wrote a `query_canvas` Cypher missing the required `$uid` scope → tool rejected → model retried the *identical* broken query → new signature loop-guard aborted at 4. Same turn it also tried to delete the protected `input` + `global` nodes (core protection blocked them). The aborted turn rolled back — no message/tool-log persisted. Guard + core-protection worked; the weaknesses are upstream: `query_canvas` ergonomics, the model targeting protected nodes, and failed turns vanishing from history.

**Goal.** Kill this class of failure: make inspection reliable, tolerate the model's most common Cypher omission, stop the model looping on protected-node deletes, and stop losing aborted turns.

All four are backend-only (`schemas.py`, `canvas_graph.py`, `executor.py`, `api/chat/stream.py`).

### A — Prefer `get_canvas_graph` for inspection (schema nudge)
- [x] `llm/tools/schemas.py`: rewrite `get_canvas_graph` desc → it is the **primary** way to see/list the canvas (all nodes incl. sessions + connections). Use for "what's on my canvas", "list/identify sessions", etc.
- [x] `llm/tools/schemas.py`: demote `query_canvas` desc → "Advanced, optional. Only for *filtered* Cypher. Prefer `get_canvas_graph` for listing." Keep the `{user_id: $uid}` example.

### B — Auto-scope `query_canvas` (tolerate the common omission)
- [x] `agent/canvas_graph.py::query_canvas`: when the Cypher omits `$uid` but matches a `(<var>:CanvasNode …)` pattern, auto-inject `{user_id: $uid}` into that node pattern via regex; only hard-error when injection is impossible (no `:CanvasNode` at all). Keep the write-keyword block.
- [x] Unit tests: missing-uid → auto-fixed + runs; already-scoped → passthrough; no `:CanvasNode` → instructive error; write keyword → blocked.

### C — Stop the model looping on protected-node deletes
- [x] `llm/tools/executor.py`: catch the "permanent infrastructure" `ValueError` from `delete_node` and return a **benign, non-`Error:`** result ("Skipped {id}: permanent infrastructure (input / global session), not deleted — continue with the rest.") so the model treats it as handled, not a failure to retry.
- [x] `api/chat/stream.py` canvas RULES: reinforce "when deleting multiple sessions, skip any `[CORE · protected]` / `[GLOBAL]` node."

### D — Persist aborted/failed turns
- [x] `api/chat/stream.py::event_generator`: on the `error` event (and the `except` branch), persist the user message + a short assistant note (partial text if any, else `⚠️ Turn aborted: <reason>`) and `commit`, so failed turns stay in history instead of rolling back. Guard against double-persist on the `done` path.

### Rollout
- [x] `python -m py_compile` changed files + run new `query_canvas` unit tests
- [x] `docker compose build api && up -d` (per docker feedback — auto)
- [x] Live verify (70B, global): list sessions → `get_canvas_graph`; malformed Cypher → auto-scoped & answers; "delete all sessions excluding global" → deletes user sessions, skips core, **no loop**; force an abort → user msg + abort note persisted
- [x] Update `BUGS.md` (new J2 entry) + `backend/CLAUDE.md` (query_canvas auto-scope, protected-delete skip, abort persistence)

---

## History
| Date       | Feature                          | Notes |
|------------|----------------------------------|-------|
| 2026-06-05 | Canvas tool robustness J2 (A+B+C+D) | root (override, implemented directly) — done, verified live; see BUGS.md J2 |
| 2026-05-31 | Pattern Detection + Triggers (#14) | root → backdir (done) |
| 2026-05-30 | Goal / Task Tracker (#13)        | root → backdir (done) → frontdir (done) |
| 2026-05-30 | User-Defined Scheduled Agents (#12) | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Scheduled Backup (#11)           | root → backdir (done) |
| 2026-05-30 | Full Data Export (#10)           | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Knowledge Graph Explorer UI (#8) | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Unified Search (#7)              | root → backdir (done) → frontdir (done) |
