# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

> History note: closed batches were removed once shipped — see git log.
> Backend Audit B1–B8 (`fde4b53`), JARVIS Fallback F1–F5 (`3e27456`),
> Core-Node Protection G1–G2 (`e7839ba`), Canvas hardening I1–I3 (`41174a3`),
> create_conversation auto-wiring regression fix (`abc70af`). All fixed.

---

## Open — Canvas hardening backlog (2026-06-02)

Follow-ups surfaced during the I1–I3 work. None are runtime-broken today; all are
hardening / cleanup that removes whole classes of future bugs. Ordered by the
recommended execution route (see bottom), not by id.

### H2 · No canvas tests — every fix is hand-verified only (P1 · safety net) — ✅ DONE

- [x] **Canvas CRUD has zero automated coverage; regressions reappear silently.**
  - **Shipped:** `backend/tests/canvas/` — 17 tests, mock driver + mock PG, no live deps (`conftest.py` `FakeDriver`/`FakeResult`). Covers create_node guards (embedded/permanent/unknown/malformed-conv-id + internal-bootstrap), delete_node (protected refused / missing raises / normal deletes), `_reap_orphan_sessions` (prunes malformed+dead, skips protected+keep-id, noop when clean), and the `_ensure_creation_wiring` `internal=True` regression guard. Run: `python -m pytest tests/canvas -v` (host). **17 passed.**
  - **Why it matters:** every fix this session (G1/G2/I1/I2/I3 + the auto-wiring regression) was verified by hand in-container. None of that survives into CI. The I2→`create_conversation` regression would have been caught instantly by one test.
  - **Where:** new `backend/tests/canvas/` mirroring the existing mock-DB pattern (`backend/tests/retrieval/conftest.py` — `AsyncMock`, no NIM, no live Neo4j). Mock `get_driver()` + `db.execute`.
  - **Assertions (pure logic):**
    - `create_node` rejects each permanent type (`input/session/memory/config`) unless `internal=True`
    - `create_node` rejects non-UUID `conversation_id`
    - `delete_node` raises `ValueError` on a `protected` node, on a missing id
    - `_reap_orphan_sessions` prunes malformed + dead conv ids, skips protected + the keep-id
    - `_ensure_creation_wiring` calls `create_node(..., internal=True)` (the regression)
  - **Cost:** ~2h. Highest durable value — it is the net under every other item here.

### H7 · `_ensure_creation_wiring` except dropped the error cause (P2 · diagnostics) — ✅ DONE

- [x] **`backend/llm/tools/executor.py` caught every exception but logged only a generic "auto-wire failed" — that is why the I2 regression was effectively silent.**
  - **Root cause:** `except Exception:` logged a message with no exception detail, so the blocked-create `ValueError` was invisible. (The broad catch itself is intentional — a wiring failure must not break the already-committed `create_conversation` success.)
  - **Shipped:** keep the broad catch but log `type(e).__name__` + the message + `node_type`, so the real cause surfaces in `docker compose logs api`.

### H5 · No escape hatch for a wrongly-protected node + no dup audit (P2 · cleanup)

- [ ] **`set_protected` only ever sets `true` and `delete_node` hard-refuses protected nodes — a wrongly-protected node is unremovable except by raw cypher.**
  - **Files:** `backend/agent/canvas_graph.py` (`set_protected`, `delete_node`).
  - **Risk:** I2 prevents *new* duplicate core nodes but does not clean any that predate it. A pre-I2 duplicate `input` would have been backfilled `protected=true` by `_ensure_canvas_wiring` → now undeletable.
  - **Fix:**
    1. One-time **audit query** (read-only) to learn if duplicates exist:
       `MATCH (n:CanvasNode) WHERE n.node_type IN ['input','memory','config'] WITH n.user_id AS u, n.node_type AS t, count(*) AS c WHERE c > 1 RETURN u, t, c`
    2. Admin-only force-delete path: `set_protected(uid, id, False)` then `delete_node`.
  - **Cost:** audit ~5m (run now); force-delete ~30m.

### H1 · Node-type policy duplicated across ≥5 places — drift risk (P2 · architecture) — ✅ DONE

- [x] **The same type-classification facts are hardcoded in ≥5 spots that must agree; adding a 13th node type means editing all of them.**
  - **Shipped:** `agent/node.py` is now the single source of truth. The `Node` dataclass gained `embedded`/`ai_creatable`/`permanent` flags; module-level `EMBEDDED_TYPES`, `AI_CREATABLE_TYPES`, `PERMANENT_TYPES`, `MANAGED_TYPES` are derived from the registry. Consumers import them: `canvas_graph.create_node` (`EMBEDDED_TYPES`/`MANAGED_TYPES`), `api/chat/stream.py` (`AI_CREATABLE_TYPES` → `_CREATABLE_NODES`), `llm/tools/schemas.py` (dynamic `create_canvas_node` description). Locked by `tests/canvas/test_node_policy.py` (6 tests — sets partition the registry, no overlap). Adding a type now = one flag.
  - **Note:** frontend `_CORE_NODES` stays only as a demo-node fallback; real nodes already guard off the backend `protected` flag (I3), so it is no longer a drift source.
  - **Duplicated in:**
    - `_NON_CANVAS_TYPES` — `backend/agent/canvas_graph.py:26`
    - `_PERMANENT_TYPES` — `backend/agent/canvas_graph.py` (I2)
    - `_PERMANENT_NODES` / `_EMBEDDED_NODES` / `_CREATABLE_NODES` — `backend/api/chat/stream.py:147-152`
    - `_CORE_NODES` — `frontend/public/canvas/{nodes,secondary-nodes,popup-nodes}.jsx`
    - prose list in `backend/llm/tools/schemas.py:71`
    - the 12-type registry — `backend/agent/node.py`
  - **Fix:** add flags to the `Node` dataclass in `agent/node.py` — `permanent` (input/memory/config, singleton, internal-create only), `embedded` (insights/goals/automations/mech), `ai_creatable` (files/logs/usage/workspace). Derive every set from the registry. Expose the flags in the `get_canvas_graph` node payload; frontend reads `node.data.permanent` instead of its own set.
  - **Cost:** ~1h, touches registry + 3 backend modules + 3 frontend files. Low risk **once H2 exists**.

### H4 · `session` type is overloaded — global vs. ordinary (P2 · design smell) — ✅ DONE

- [x] **One `node_type="session"` means two things: the permanent protected global JARVIS session AND ordinary user/AI-created sessions.**
  - **Shipped:** an explicit `config.kind` marker. `_ensure_canvas_wiring` writes `kind:"global"` on the JARVIS session (idempotent backfill via `update_node` each `/global` load); `_ensure_creation_wiring` tags AI/user sessions `kind:"user"`. The injected CANVAS STATE now renders `[GLOBAL]` vs `[user session]`, and the node-inventory RULE references `[GLOBAL]` explicitly — the model no longer infers global-ness from a conversation_id match. Regression test asserts `kind="user"` on the creation path.
  - **Verified live:** both global sessions (user 1 + user 2) backfilled to `protected=true, kind=global`; ordinary sessions render as `[user session]`.
  - **Why it matters:** this conflation is exactly why I2 broke `create_conversation` — "session" could not be blanket-blocked without killing legitimate creation. Today the only distinguisher is the `protected` flag + a `conversation_id == JARVIS` match. The model also hallucinates here ("delete the session").
  - **Fix:** add an explicit marker — `config.kind: "global"|"user"` (cheaper) or a distinct `global_session` registry type. Permanence / UI / prompt rules then key off an explicit field instead of inferring identity from the conv id.
  - **Cost:** ~1h. Pairs naturally with H1 (do them together).

### H6 · create paths don't dedup `session`/`input` (P3) — ✅ DONE

- [x] **`create_node` now dedups — no second node for the same logical entity.**
  - **Shipped:** `_find_duplicate(user_id, node_type, config)` in `backend/agent/canvas_graph.py`; `create_node` returns the existing id instead of creating when a duplicate exists. Singletons (`input`/`memory`/`config`) dedup by type (preferring the protected node); `session` dedups by `conversation_id`, `workspace` by `workspace_id`. Idempotent for every caller (AI tool, REST, both bootstrap paths). Locked by 2 tests (`test_dedup_singleton_returns_existing`, `test_dedup_session_by_conversation_id`).
  - **Verified live:** a second `create_node(1, "input")` / `create_node(1, "session", conv)` returns the existing protected id, no new node.
  - **Cleanup done (via H3 reconcile):** user 2's pre-existing duplicates collapsed — `f587a983` (extra `input`) + `77ab9bb4` (duplicate conv `061ca3d9` `session`) pruned; protected nodes kept. Final: user 2 = 1 input + 2 sessions (global + one real). Second pass = no-op (idempotent).

### H3 · Reaper runs only on `/global`, not periodically (P3 · belt-and-suspenders) — ✅ DONE

- [x] **Reconcile (reap orphans + collapse duplicates) now runs periodically for every user, not only on `/canvas/` load.**
  - **Shipped:** `reconcile_canvas(user_id, db)` in `backend/agent/canvas_graph.py` = `_reap_orphan_sessions` (malformed/dead conv ids) + `_collapse_duplicate_nodes` (singleton `input`/`memory`/`config` + same-conv `session`, always keeping the protected node). `_reap_orphan_sessions` + `_prune_node` moved here from `api/canvas.py`; `list_canvas_user_ids()` added. `scheduler_worker.py` runs `run_canvas_reconcile()` on a **6-hour interval** (`__canvas_reconcile__`), with `init_neo4j()`/`close_neo4j()` on the scheduler lifecycle. `api/canvas.py` `_ensure_canvas_wiring` calls the same `reconcile_canvas` on boot. Idempotent.
  - **Infra:** `docker/docker-compose.yml` scheduler service now sets `NEO4J_URI` + `NEO4J_PASSWORD` and `depends_on neo4j: service_healthy` (it previously had no Neo4j env → graph memory disabled in the scheduler).
  - **Tests:** `test_reaper.py` rewritten against `agent.canvas_graph` — `test_reaper_prunes_malformed_and_dead_keeps_valid` + `test_collapse_duplicate_inputs_and_sessions`. **25 passed.**
  - **Verified live:** scheduler connects to Neo4j on boot; manual `run_canvas_reconcile()` pruned the two user-2 dups, second pass no-op.

---

## Summary

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| H2 | No canvas tests (CRUD coverage) | P1 | ✅ Fixed |
| H7 | `_ensure_creation_wiring` except dropped error cause | P2 | ✅ Fixed |
| H5 | No force-delete for protected node + dup audit | P2 | Audit done · tool deferred (no protected dups) |
| H1 | Node-type policy duplicated ≥5 places (drift) | P2 | ✅ Fixed |
| H4 | `session` type overloaded (global vs ordinary) | P2 | ✅ Fixed |
| H6 | create paths don't dedup session (+ input) | P3 | ✅ Fixed (cleanup done) |
| H3 | Reaper not periodic (only `/global`) | P3 | ✅ Fixed |
| | **Open total** | | **0 open** |

> **Phase 0 audit result (2026-06-02):** no wrongly-protected duplicate core nodes →
> H5 force-delete deferred. Cleaned: `user 99/py-test-1` junk + user 2's 3 orphan
> sessions (reconcile). User-2's remaining duplicate `input` + duplicate "Bug Tracking"
> session were collapsed by the **H3** periodic reconcile (self-healing, idempotent).
