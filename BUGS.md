# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

> History note: the Backend Audit (B1–B8), JARVIS Fallback Cascade (F1–F5), and Canvas
> Core-Node Protection (G1–G2) batches are all fixed and shipped — see git log
> (`fde4b53`, `3e27456`, `e7839ba`). They were removed from this file once closed.

---

## Open — Canvas hardening follow-ups (2026-06-02)

Surfaced by the G1/G2 verification. None are runtime-broken; all three are hardening / cleanup.

### I1 · Stray orphan session node on the live canvas (P2 · data, not code)

- [x] **A hallucinated `session` node points to a non-existent conversation and renders as a dead node.**
  - **Where:** Neo4j, `user_id = 1`. Node `9e994470-09a5-438a-bda3-e69f09968c43`,
    `node_type = "session"`, `config.conversation_id = "d3c4b1a2-c3d4e5f6g7h8i9j0k"`.
  - **Symptoms:**
    - The `conversation_id` is a **malformed UUID** (`g7h8i9j0k` are not hex) — no matching row exists in Postgres `conversations`. It was invented by an 8B hallucination during the pre-F4 fallback cascade (the same class of event that the F4 fix now prevents).
    - `protected = NULL/false` (confirmed in the G1 verification dump), so it is deletable — but nothing deletes it automatically, and it has no real conversation behind it.
    - It clutters the JARVIS canvas and can confuse the model's node inventory (a session it can "open" that leads nowhere).
  - **Why it persists:** there is no orphan-reaper. `_ensure_canvas_wiring` (`backend/api/canvas.py:149`) only *adds/heals* the input + global session; it never prunes sessions whose `conversation_id` has no Postgres row.
  - **Fix (data, one-off):** delete it directly —
    `MATCH (n:CanvasNode {user_id:1, node_id:"9e994470-09a5-438a-bda3-e69f09968c43"}) DETACH DELETE n`
    via `docker compose exec -T neo4j cypher-shell -u neo4j -p changeme`.
  - **Fix (shipped, durable):** `_ensure_canvas_wiring` now takes `db` and calls `_reap_orphan_sessions` (`backend/api/canvas.py`). On every `/global` load it drops any unprotected `session` node whose `conversation_id` is malformed (UUID parse fails) or has no matching `conversations` row; protected nodes and the just-ensured global session are skipped. Runs on every canvas boot — no migration, no manual cypher.
  - **Verified live:** stray `9e994470` (conv `d3c4b1a2-…g7h8`) was reaped on the first `_ensure_canvas_wiring` run; Neo4j now holds only the 2 protected core nodes.

### I2 · AI can still *create* duplicate core nodes (P1 · backend not enforced)

- [x] **`create_node` blocks the 4 embedded types but not the 4 permanent/core types — the model can spawn a second `input`/`session`/`memory`/`config` node.**
  - **Files:**
    - `backend/agent/canvas_graph.py:70-78` — `create_node` rejects only `_NON_CANVAS_TYPES = {"insights","goals","automations","mech"}` (`:26`). Any other registered type, including `input/session/memory/config`, is created with no dedup and no permanence check.
    - `backend/api/chat/stream.py:147-152` — the prompt's `_PERMANENT_NODES = {"input","session","memory","config"}` is excluded from `_CREATABLE_NODES`, so the model is *told* not to create them, but this is prompt-only guidance; nothing enforces it server-side.
    - `backend/llm/tools/executor.py` — `create_canvas_node` calls `create_node` directly, so a hallucinated tool call bypasses the prompt rule entirely.
  - **Symptoms / blast radius:**
    - This is exactly how the I1 orphan was born: the model emitted a `create_canvas_node(node_type="session", …)` with an invented `conversation_id`, and the backend happily created it.
    - A duplicate `input` node has no dedup either — two input nodes would both be backfilled `protected=true` by `_ensure_canvas_wiring` and become **undeletable clutter** (G1 now blocks removing them).
  - **Fix (shipped):** `create_node` gained `internal: bool = False` (`backend/agent/canvas_graph.py`). It rejects `_PERMANENT_TYPES = {"input","session","memory","config"}` unless `internal=True`; only `_ensure_canvas_wiring` passes `internal=True`, so the AI tool + REST path are blocked. **Bonus hardening:** `create_node` also rejects any `config.conversation_id` that fails `uuid.UUID()` parsing — stops the hallucinated-id class at the door (the exact mechanism that birthed I1).
  - **Verified live:** AI-path `create_node` of all 4 permanent types → `ValueError("… permanent infrastructure managed automatically …")`; malformed `conversation_id` → `ValueError("Invalid conversation_id …")`; the `internal=True` bootstrap still creates/heals the global session.

### I3 · Frontend `_CORE_NODES` guard never matches real (Neo4j) nodes (P3 · cosmetic, now redundant)

- [x] **The UI close-button guard keys off static demo string ids, so it does nothing for UUID-backed nodes — protected nodes still show a delete (✕) button that 400s on click.**
  - **Files (identical guard, three copies):**
    - `frontend/public/canvas/nodes.jsx:17` — `const _CORE_NODES = new Set(['input','session','memory','config'])`; used at `:19` `const canClose = !_CORE_NODES.has(nodeId)`.
    - `frontend/public/canvas/secondary-nodes.jsx:13` (used `:15`).
    - `frontend/public/canvas/popup-nodes.jsx:36` (used `:38`).
  - **Root cause:** the guard compares `nodeId` against the literal type strings `'input'/'session'/...`. Those match only the **static demo nodes**. Real nodes from Neo4j render with `nodeId = "ai-{uuid}"` (e.g. `ai-0741d809-…`), so `_CORE_NODES.has(nodeId)` is always `false` → `canClose` is always `true` → the ✕ button renders on the actual protected input + global-session nodes.
  - **Symptoms / blast radius:**
    - Clicking ✕ on a real protected node fires `_closeNode(nodeId)` → `DELETE /api/canvas/nodes/{id}` → backend G1 returns **400 `Cannot delete core node …`**. The node correctly survives (backend enforces), so this is **not** a data-loss bug — purely a misleading affordance + a wasted failing request.
  - **Fix (shipped):** both `neoToRF` mappers (`Canvas.jsx`, `canvas-live.js`) now stamp `data.protected = !!n.protected` and add protected RF ids (`ai-{uuid}`) to `window.NIM_PROTECTED_IDS`. The three guards (`nodes.jsx:19`, `secondary-nodes.jsx:15`, `popup-nodes.jsx:38`) became `canClose = !_CORE_NODES.has(nodeId) && !window.NIM_PROTECTED_IDS?.has(nodeId)` — the ✕ button now hides on any backend-protected node. `_CORE_NODES` stays as the demo-node fallback.
  - **Note:** static-bundle JS (no build step) — takes effect on next browser load of `/canvas/`; backend G1 already prevents the delete regardless, so this only removes the misleading affordance.

---

## Summary

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| I1 | Stray orphan session node (`9e994470`, dead conv id) | P2 | ✅ Fixed |
| I2 | AI can create duplicate `input/session/memory/config` nodes | P1 | ✅ Fixed |
| I3 | Frontend `_CORE_NODES` guard dead for UUID nodes (✕ button 400s) | P3 | ✅ Fixed |
| | **Total** | | **3 fixed · 0 open** |
