# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

---

## Backend Audit — 2026-06-01

Scope: full `backend/` scan. pyflakes across all 164 files → only one undefined name (#B1). Remaining items found by tracing the modified canvas/creation flow.

### P0 — Broken at runtime

- [x] **B1 · `update_node` not imported → `update_canvas_node` tool always fails**
  - **Files:** `backend/llm/tools/executor.py:16-19` (import block), `:93` (call site)
  - **Root cause:** import from `agent.canvas_graph` lists `create_node, delete_node, find_nodes, wire_nodes, unwire_nodes, query_canvas, get_canvas_graph` — `update_node` is missing. `update_node` exists (`canvas_graph.py:120`) and is imported correctly in `api/canvas.py:11`, but not here.
  - **Blast radius:** every `update_canvas_node` tool call raises `NameError: name 'update_node' is not defined`, caught by the `except` at `executor.py:149`, so the model receives `"Error: name 'update_node' is not defined"`. AI can never update a node's config/status. REST `PATCH /canvas/nodes/{id}` is unaffected.
  - **Fix:** add `update_node` to the import block.

### P1 — Silent failures / data corruption

- [x] **B2 · Workspace auto-wire uses wrong port → always fails silently**
  - **Files:** `backend/llm/tools/executor.py:353-356`, `backend/agent/node.py:87`
  - **Root cause:** `_ensure_creation_wiring()` hardcodes `dst_port="message"` for both session and workspace. Workspace's only input port is `workspace_id` (node.py:87), not `message`. `wire_nodes()` validates ports (`canvas_graph.py:233`) and raises `ValueError` → swallowed by the bare `except` at `executor.py:357`.
  - **Blast radius:** auto-created workspace canvas node is never wired to the input node. (Session path works — session input port is `message`.)
  - **Fix:** pick `dst_port` by type — `"message"` for session, `"workspace_id"` for workspace (matches the system-prompt instructions in `api/chat/stream.py`).

- [x] **B3 · Duplicate session/workspace canvas nodes** — kept auto-wire, removed manual create_canvas_node/wire_nodes steps from system prompt.
  - **Files:** `backend/llm/tools/executor.py:125,147` (calls `_ensure_creation_wiring`), `:321-358`, `backend/agent/canvas_graph.py:66` (`create_node`, no dedup), `backend/api/chat/stream.py` node-inventory prompt (SESSION/WORKSPACE CREATION steps)
  - **Root cause:** two creation paths run for one entity. The `create_conversation`/`create_workspace` tool *itself* calls `_ensure_creation_wiring()` which creates the canvas node and wires it. The system prompt *then* tells the model to also call `create_canvas_node(...)` + `wire_nodes(...)` (steps 2-3). Ordering: the executor's auto-wire runs first (model hasn't called create_canvas_node yet), so `_ensure_creation_wiring`'s dedup-by-`conversation_id` (executor.py:330-335) doesn't help — the model's later `create_canvas_node` has no dedup and makes a second node.
  - **Blast radius:** two `session` (or `workspace`) nodes per created entity, plus a duplicate/invalid wire. Canvas clutter + confused graph state.
  - **Fix:** pick one owner. Either drop `_ensure_creation_wiring` and let the model do steps 2-3, or keep auto-wiring and remove steps 2-3 from the prompt. Recommend keeping auto-wire (deterministic) and changing the prompt to "the session/workspace node is created and wired automatically — do not call create_canvas_node for it."

- [x] **B4 · No `canvas_update` SSE after `create_conversation`/`create_workspace`**
  - **Files:** `backend/api/chat/stream.py:44-47` (`_CANVAS_WRITE_TOOLS`), `:331`
  - **Root cause:** `_CANVAS_WRITE_TOOLS` lists only `create_canvas_node/delete_canvas_node/update_canvas_node/wire_nodes/unwire_nodes`. But `create_conversation`/`create_workspace` mutate the canvas through `_ensure_creation_wiring`. Their `tool_result` does not match the set, so no `canvas_update` event is emitted.
  - **Blast radius:** the auto-created node never triggers a frontend `GET /canvas/graph` re-fetch — it stays invisible until the user manually refreshes. (Masked today by B3 because the model's own `create_canvas_node` does emit the event — fix B3 and this surfaces.)
  - **Fix:** add `create_conversation`, `create_workspace` to `_CANVAS_WRITE_TOOLS`.

### P2 — Regressions / spec gaps

- [x] **B5 · Token buffering kills incremental streaming** — stream tokens live again; emit `preamble_discard` SSE when a tool call follows streamed text. Frontend (`useStreamChat.js`, `canvas-sse.js`) clears the streamed preamble on that event; api layer clears its accumulator so the persisted message holds only the final answer.
  - **Files:** `backend/llm/service/stream.py:196-211`
  - **Root cause:** tokens are appended to `_token_buffer` inside the `async for`, and only flushed (`yield {"type": "token"}`) *after* the upstream stream fully completes. Done to discard preamble when a tool call follows (NIM signals tool calls only at end-of-stream, so buffering is the only way to know). Side effect: the final text answer no longer streams — every token is held until generation finishes, then dumped at once.
  - **Blast radius:** time-to-first-token for any non-tool reply ≈ full generation latency. SSE streaming UX is effectively gone for normal answers.
  - **Fix options:** (a) accept the trade-off and document it; (b) stream tokens live and instead suppress/replace preamble on the frontend when a `tool_call` event arrives; (c) only buffer when `tools` is non-None (tool loop active), stream directly otherwise.

- [x] **B6 · `create_canvas_node` still accepts `insights`/`goals`/`automations`/`mech`**
  - **Files:** `backend/agent/canvas_graph.py:66-69` (no type guard), `backend/llm/tools/schemas.py:71`, `backend/api/chat/stream.py` (`_CREATABLE_NODES` lists them)
  - **Root cause:** the resolved Canvas Planning Gap (this file, line 21-24) says these 4 types are not standalone nodes and `create_canvas_node` "must guard against these 4 types and reject them." Not enforced: `create_node` creates any type in the registry; the tool schema description and the prompt's CREATABLE list both advertise them.
  - **Blast radius:** model can spawn orphan `insights/goals/automations/mech` canvas nodes the UI has no real home for.
  - **Fix:** reject these 4 in `create_node` (or in the executor), and drop them from the schema description + `_CREATABLE_NODES`.

### P3 — Doc drift (code vs `backend/CLAUDE.md`)

- [x] **B7 · `MAX_TOOL_ITERATIONS` changed 10 → 20**
  - **Files:** `backend/llm/service/stream.py:15`; stale in `backend/CLAUDE.md:18,97`, root `CLAUDE.md` "Tool loop guard" row.
- [x] **B8 · Auto-wire relation/port doc mismatch**
  - **Files:** `backend/CLAUDE.md:146` says relation `manages`, `routed_message → message`. Code uses `relation="routes_to"`, `dst_port="message"` for session (`executor.py:355`). Workspace prompt uses `workspace_id`/`manages`. Align doc to code (and to B2 fix).

### Notes (not bugs, worth a decision)

- Fire-and-forget `asyncio.create_task(compress_history/update_memory/update_project_summary)` at `stream.py:369-372` — previously flagged as inconsistent with the ARQ job system; also unreferenced tasks can be GC'd mid-flight and they open their own DB sessions outside request scope. Consider enqueuing via ARQ.
- Unused imports across ~25 files (pyflakes) — harmless but noisy; e.g. `llm/service/stream.py:11,13`, `api/chat/stream.py:16-17`, `api/chat/background.py:1` (`asyncio`). Cleanup only.

---

## Summary

| Area | Total | Fixed | Open |
|------|-------|-------|------|
| Canvas Planning Gaps | 3 | 3 | 0 |
| Documentation Inconsistencies | 9 | 9 | 0 |
| Canvas Runtime Bugs | 1 | 1 | 0 |
| Backend Audit 2026-06-01 | 8 | 8 | 0 |
| **Total** | **21** | **21** | **0** |
