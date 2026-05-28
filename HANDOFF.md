# HANDOFF
- Updated: 2026-05-28
- Status: done
- Archive: `HANDOFF_ARCHIVE.md` (completed features; see Archive rules in root CLAUDE.md)

---

## Completed: Re-embed on MODEL_EMBEDDING change + Graph Memory (Neo4j)

### What was built
- **Neo4j** service in docker-compose; async driver; fails open if `NEO4J_PASSWORD` unset
- **Graph extraction**: `extract_and_store()` fires post-reply; entities + relations stored per user
- **Graph context**: injected as `[GRAPH CONTEXT]` in system messages when memory enabled
- **`query_graph` tool**: available in agent loop; calls `query_by_term(user_id, term)`
- **`GET /api/graph/stats`**: returns `{available, entities, relations}` scoped to current user
- **Graph tab**: 5th tab in Memory panel; auto-refreshes 2s after each AI reply
- **Re-embed**: startup compares `MODEL_EMBEDDING` env vs `system_config` DB row; queues ARQ batches of 100 on mismatch
- **`POST /api/admin/re-embed`**: manual trigger; admin-only; returns `{"queued": <int>}`
- **↺ Re-embed All** button in admin Invite panel

### Key files
| File | Role |
|------|------|
| `backend/core/neo4j_client.py` | async driver, init/close, constraint setup |
| `backend/llm/graph_memory.py` | extract_and_store, query_context, query_by_term |
| `backend/api/graph.py` | GET /api/graph/stats |
| `backend/services/re_embed.py` | check_and_queue_re_embed, queue_re_embed_force |
| `backend/alembic/versions/026_system_config.py` | system_config table migration |
| `backend/models.py` | SystemConfig model |

### Env vars added
| Var | Default | Notes |
|-----|---------|-------|
| `NEO4J_URI` | `bolt://neo4j:7687` | |
| `NEO4J_USER` | `neo4j` | |
| `NEO4J_PASSWORD` | — | required to enable graph; blank = disabled |

---

## History
| Date | Feature | Notes |
|------|---------|-------|
| 2026-05-28 | Re-embed + Graph Memory | All stages complete; committed b972e66 |
