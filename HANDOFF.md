# HANDOFF
- Updated: 2026-06-09
- Status: done
- Owner: root

---

## Active Task: Remove Canvas Feature

**Why.** The autonomous canvas (7 AI tools, Neo4j node graph, 3-layer creation guard,
J1 intent gate) required more guardrails than it provided autonomy. Every chat request
paid canvas overhead regardless of whether canvas was used. Decision: strip it entirely.
The Neo4j Entity graph (graph_memory.py) is unaffected. agent_scratchpad DB column stays.

---

### Task Checklist

**Delete entirely:**
- [ ] `rm backend/api/canvas.py`
- [ ] `rm -rf backend/agent/`
- [ ] `rm -rf frontend/public/canvas/`
- [ ] `rm -rf backend/tests/canvas/`

**backend/main.py**
- [ ] Remove `from api.canvas import router as canvas_router`
- [ ] Remove `app.include_router(canvas_router)`

**backend/llm/tools/schemas.py**
- [ ] Remove `from agent.node import AI_CREATABLE_TYPES`
- [ ] Remove 8 tool entries from TOOL_SCHEMAS: create_canvas_node, delete_canvas_node,
      update_canvas_node, wire_nodes, unwire_nodes, query_canvas, get_canvas_graph, create_conversation
- [ ] Remove `_CANVAS_TOOL_NAMES` frozenset
- [ ] Remove `CANVAS_TOOL_SCHEMAS` variable
- [ ] Simplify: `FILE_TOOL_SCHEMAS = TOOL_SCHEMAS`

**backend/llm/tools/__init__.py**
- [ ] Remove `canvas_context_active` from import and from `__all__`

**backend/llm/tools/executor.py**
- [ ] Remove `from agent.canvas_graph import (...)` import block
- [ ] Remove `_STATIC_CANVAS_NODES` dict
- [ ] Remove `_CANVAS_INTENT_RE` + `canvas_context_active()` function
- [ ] Remove creation guard: `_CREATION_RE`, `_NEGATION_RE`, `_CONFIRMATION_RE`,
      `_run_creation_guard()`, `_ensure_creation_wiring()`
- [ ] Remove 8 dispatch branches: 7 canvas tools + create_conversation

**backend/llm/service/stream.py**
- [ ] Remove `CANVAS_TOOL_SCHEMAS`, `canvas_context_active` from imports
- [ ] Remove `_READONLY_CANVAS_TOOLS` frozenset
- [ ] Remove `canvas_tools` variable + gating block
- [ ] Remove `canvas_tools` from tool list merge
- [ ] Remove `boot_log`, `node_inventory`, `canvas_state` from `generate_stream()` signature + call sites

**backend/llm/service/context.py**
- [ ] Remove `boot_log`, `node_inventory`, `canvas_state` params from `build_context_messages()`
- [ ] Remove `boot_blocks` construction and prepend

**backend/api/chat/stream.py**
- [ ] Remove imports: agent.boot, agent.node, agent.scratchpad, canvas_context_active
- [ ] Remove `_CANVAS_WRITE_TOOLS` frozenset
- [ ] Remove canvas_active / boot_report / boot_log / last_session block (~lines 137-145)
- [ ] Remove node inventory block (~lines 148-171)
- [ ] Remove canvas state block + inline uuid import + Postgres title query (~lines 173-211)
- [ ] Remove canvas gate block (lines 218-220)
- [ ] Remove canvas params from compare + stream call sites
- [ ] Remove canvas stage activity append
- [ ] Remove canvas_update SSE event emission
- [ ] Remove update_scratchpad call + try/except

**backend/services/scheduler_worker.py**
- [ ] Remove `from agent.reconcile import list_canvas_user_ids, reconcile_canvas`
- [ ] Remove `run_canvas_reconcile()` function
- [ ] Remove canvas reconcile APScheduler job

**backend/tests/scheduler/test_sync_preserves_internal_jobs.py**
- [ ] Remove `__canvas_reconcile__` from `INTERNAL` list

---

### Do NOT touch
- `backend/models/user.py` — agent_scratchpad stays
- `backend/alembic/versions/036_*` — no migration rollback
- `backend/core/neo4j_client.py` — Entity graph still in use
- `backend/llm/graph_memory.py` — unaffected

---

### Verify
- [ ] `grep -r "from agent" backend/` → zero results
- [ ] `grep -r "canvas_context_active\|CANVAS_TOOL\|node_inventory\|boot_log\|agent_boot" backend/` → zero results
- [ ] `python -m py_compile` on all 9 modified files — no errors
- [ ] `docker compose build api && docker compose up -d api`
- [ ] Chat message: normal turn completes, no canvas events in SSE
- [ ] Chat message with file: file tools work, no canvas tools offered
- [ ] `GET /canvas/graph` → 404

### Recorded
- All 10 tasks complete. Canvas feature fully removed.
- No new endpoints, env vars, or DB columns.
- `agent_scratchpad` JSONB column (migration 036) and Neo4j Entity graph untouched.
- `core/neo4j_client.py:41-42` still creates `canvas_user_id` index on `CanvasNode` label — harmless dead code (IF NOT EXISTS guard), HANDOFF said not to touch.
- Bug fix included: `last_session` was incorrectly gated by `canvas_active` in `api/chat/stream.py`; now always passed.
- Verified: normal chat SSE clean (no canvas events); file chat uses `read_file` tool correctly; `GET /canvas/graph` → 404.
- backend/CLAUDE.md needs update to remove canvas architecture sections (Agent Canvas Architecture, Creation Guard, Boot Sequence, System Prompt Injection).

---

## History
| Date       | Feature                          | Notes |
|------------|----------------------------------|-------|
| 2026-06-06 | Canvas feature removal           | root → backend |
| 2026-06-05 | Canvas tool robustness J2 (A+B+C+D) | done, verified live; see BUGS.md J2 |
| 2026-05-31 | Pattern Detection + Triggers (#14) | root → backdir (done) |
| 2026-05-30 | Goal / Task Tracker (#13)        | root → backdir (done) → frontdir (done) |
| 2026-05-30 | User-Defined Scheduled Agents (#12) | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Scheduled Backup (#11)           | root → backdir (done) |
| 2026-05-30 | Full Data Export (#10)           | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Knowledge Graph Explorer UI (#8) | root → backdir (done) → frontdir (done) |
| 2026-05-30 | Unified Search (#7)              | root → backdir (done) → frontdir (done) |
