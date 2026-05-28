# HANDOFF
- Updated: 2026-05-28 · frontdir
- Status: done

---

## Active Feature: Re-embed on MODEL_EMBEDDING change + Graph Memory (Neo4j)

Execute in order: **backdir (done)** → **dockdir** → **frontdir** → root

---

## backdir ✓
### Tasks
- [x] Add `SystemConfig` model to `models.py`
- [x] Migration `026_system_config.py`
- [x] `services/re_embed.py` — `check_and_queue_re_embed()` + `queue_re_embed_force()`
- [x] `services/arq_worker.py` — add `re_embed_batch_job`; register in `WorkerSettings.functions`
- [x] `main.py` — call `check_and_queue_re_embed()` + `init_neo4j()` in lifespan; `close_neo4j()` on shutdown
- [x] `api/admin.py` — `POST /admin/re-embed` endpoint
- [x] `requirements.txt` — add `neo4j>=5.0.0`
- [x] `config.py` — add `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- [x] `core/neo4j_client.py` — async driver; skips gracefully if `NEO4J_PASSWORD` unset
- [x] `llm/graph_memory.py` — `extract_and_store()` + `query_context()` + `query_by_term()`
- [x] `llm/service/context.py` — `graph_context` param → inject `[GRAPH CONTEXT]` block after `[WORKSPACE STATE]`
- [x] `llm/service/stream.py` — `graph_context` param, passed through to `build_context_messages`
- [x] `api/chat/helpers.py` — call `graph_query()` in `_build_stream_context`, return `graph_context`
- [x] `api/chat/router.py` — pass `graph_context` to `generate_stream`; fire `extract_and_store` task after reply
- [x] `llm/tools.py` — add `query_graph` tool schema + execute handler

### Recorded
- **New DB table**: `system_config (key VARCHAR PK, value TEXT, updated_at TIMESTAMPTZ)`
- **Migration**: `026_system_config.py` (revises 025)
- **New ARQ job**: `re_embed_batch_job(ctx, table: str, offset: int, batch_size: int)` — table is `"file_chunk"` or `"message_embedding"`
- **New admin endpoint**: `POST /api/admin/re-embed` → `{"queued": <int>}` — requires admin JWT
- **New env vars**: `NEO4J_URI` (default `bolt://neo4j:7687`), `NEO4J_USER` (default `neo4j`), `NEO4J_PASSWORD` (required for graph; skipped if blank)
- **Graph schema**: `(:Entity {user_id: int, name: str, type: str, updated_at: str})-[:RELATED_TO {type: str, updated_at: str}]->(:Entity)`
- **Graph context**: injected as `[GRAPH CONTEXT]` block in system messages when memory_enabled=true; only when Neo4j is up
- **New tool**: `query_graph(query: str)` — available in agent tool loop; calls `query_by_term(user_id, term)`
- **Re-embed trigger**: on startup compares `MODEL_EMBEDDING` env vs `system_config` row; queues ARQ batches of 100 if mismatch
- **Neo4j fails open**: if `NEO4J_PASSWORD` blank or host unreachable, all graph calls are no-ops; no crash

---

## dockdir ✓
### Tasks
- [x] Add `neo4j` service to `docker-compose.yml`
- [x] Add `neo4jdata` to top-level `volumes:` block
- [x] Add `NEO4J_PASSWORD` + `NEO4J_URI` to `api` and `arq-worker` environment blocks
- [x] Add `neo4j` as `depends_on` for `api` and `arq-worker` (condition: service_healthy)
- [x] Update `.env.example` — added Neo4j section
- [x] Rebuild api + arq-worker; `docker compose up -d` — all services healthy
- [x] Migration: table already existed from prior dev run; stamped alembic to 026 (head)
- [x] Verified Neo4j browser at http://localhost:7474 returns 200

### Recorded
- **neo4j service**: `neo4j:5`, ports 7474/7687, volume `neo4jdata`, healthcheck via `wget http://localhost:7474`
- **Auth**: `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-changeme}`; default password `changeme`
- **api + arq-worker**: receive `NEO4J_URI=bolt://neo4j:7687` and `NEO4J_PASSWORD` via env; both `depends_on neo4j: condition: service_healthy`
- **Migration note**: `system_config` table was created in a prior dev session; alembic was at 025 → stamped to 026 (no DDL run needed)

---

## frontdir ✓
### Tasks
- [x] Add **Graph Memory** tab in Memory panel:
  - Created `backend/api/graph.py` → `GET /api/graph/stats` returns `{available, entities, relations}`
  - Registered router in `main.py`
  - Added "Graph" tab to Memory panel tabs (Chat.jsx)
  - Tab shows entity/relation count cards when Neo4j is available; graceful "unavailable" message if not
- [x] Re-embed admin button: added "↺ Re-embed All" button in Invite panel admin section → `POST /api/admin/re-embed` → shows queued count or error

### Recorded
- **New endpoint**: `GET /api/graph/stats` → `{available: bool, entities: int, relations: int}` — requires auth, scoped to current user
- **New file**: `backend/api/graph.py`
- **Graph tab**: added as 5th tab in Memory panel; loads on tab click; refresh button available
- **Re-embed button**: in Invite panel "⚙ Embeddings" section; shows result message after POST; admin-only panel gate already enforced by `userRole === 'admin'` check in the header button
- **Known issue**: `GET /api/graph/stats` uses a single Cypher query with `OPTIONAL MATCH` for relations — if a user has 0 entities, the OPTIONAL MATCH still returns one row with `entities=0, relations=0` (correct behavior)
- **Known issue**: `invite_router` in `main.py` already includes `/api/auth/invites` endpoint, but the new `graph_router` prefix is `/graph` (not `/api/graph`) — the vite proxy rewrites `/api` → `localhost:8000`, so all fetch calls use `/api/graph/stats` which the proxy forwards to `localhost:8000/graph/stats`. This is consistent with how all other routes work.

---

## History
| Date | Who | Change |
|------|-----|--------|
| 2026-05-28 | root | Created — template stub |
| 2026-05-28 | backdir | Re-embed + Graph Memory — backend complete; dockdir next |
| 2026-05-28 | dockdir | Neo4j service wired; all services healthy; frontdir next |
| 2026-05-28 | frontdir | Graph stats endpoint + Memory Graph tab + Re-embed button — all done; moving to root |
