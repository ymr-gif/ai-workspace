# HANDOFF ARCHIVE
Completed features — full detail. See Archive rules in root CLAUDE.md.

---

## Re-embed on MODEL_EMBEDDING change + Graph Memory (Neo4j)
**Completed:** 2026-05-28

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
| `backend/core/neo4j_client.py` | async driver, init/close, constraint + fulltext index setup |
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

## Graph Memory — Fulltext Index + Big Limit + Score Threshold
**Completed:** 2026-05-28

### What was built
- **Fulltext index**: `entity_name_ft` created at startup in `neo4j_client.py` (Lucene-backed)
- **`query_context`**: swapped `CONTAINS` scan → `db.index.fulltext.queryNodes`; limit raised 8→50; added `min_score=0.5` Cypher filter
- **`query_by_term`**: forwards `min_score` param
- Call site `api/chat/helpers.py:212` passes `limit=50`

### Key files
| File | Change |
|------|--------|
| `backend/core/neo4j_client.py` | CREATE FULLTEXT INDEX entity_name_ft |
| `backend/llm/graph_memory.py` | fulltext query, limit=50, min_score=0.5 |
| `backend/llm/service/context.py` | call site updated to limit=50 |

---

## Bug fixes — 8 confirmed
**Completed:** 2026-05-28

### What was fixed
1. **Rate limiter keying** — `rate_limiter/rate_limiter.py`: decode JWT in `get_key()`; key by `user:<sub>`, fallback to IP
2. **File upload workspace trust** — `api/files/router.py`: UUID parse + `ws.user_id == current_user.id` check
3. **Observability schema mismatch** — `observability/metrics_worker.py`: `"type"` → `"event_type"`, `"action"` → `"operation"`, `"circuit"` → `"circuit_breaker"`
4. **Retrieval grounding** — `llm/retriever.py`, `llm/service/context.py`: `_rrf_merge` returns `list[dict]` with `{content, score, source}`
5. **Chat persistence partial-fail** — `api/chat/router.py`, `api/chat/helpers.py`: flush before stream, single commit covers user+assistant, embed retries once
6. **Memory write race** — `api/memory.py`: `SELECT ... FOR UPDATE` on UserMemory row
7. **Processor marks ready too early** — `services/processor.py`: `saved == 0` → status `"error"`; mark `"ready"` only when `saved > 0`
8. **Usage N+1** — `api/usage.py`: single `GROUP BY` query replaces per-conv loop
