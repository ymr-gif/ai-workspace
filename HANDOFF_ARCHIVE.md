# HANDOFF ARCHIVE
Completed features — full detail. See Archive rules in root CLAUDE.md.

---

## RAG Provenance Pipeline
**Completed:** 2026-05-28

### What was built
- All retrieval functions return `chunk_id`, `source_id`, `dense_score`, `sparse_score`, `final_score`, `retrieval_type` on every hit
- Fields propagated through `ctx["retrieved"]` and `ctx["file_chunks"]`

### Key files
| File | Change |
|------|--------|
| `backend/llm/retriever.py` | provenance fields on all retrieve fns |
| `backend/llm/service/context.py` | passes hits with provenance into ctx |

---

## Provenance in `done` SSE Event
**Completed:** 2026-05-28

### What was built
- `POST /chat/stream` `done` event now includes `provenance` field
- Built from deduped merge of `ctx["retrieved"]` + `ctx["file_chunks"]`; `content` stripped; UUIDs stringified; deduped by `chunk_id`
- Empty list `[]` when no RAG hits

### Shape
```json
"provenance": [
  {
    "chunk_id":       "uuid-str",
    "source_id":      "uuid-str or null",
    "dense_score":    0.015748,
    "sparse_score":   0.0,
    "final_score":    0.015748,
    "retrieval_type": "vector"
  }
]
```

### Key files
| File | Change |
|------|--------|
| `backend/api/chat/router.py` | provenance block before `event["conversation_id"]` in `done` handler |
| `backend/CLAUDE.md` | documented provenance field in API Routes |

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

## Hybrid Fusion Tuning
**Completed:** 2026-05-28

### What was built
- **Weighted fusion mode**: new `_weighted_merge()` — normalizes raw cosine sim + ts_rank to [0,1], final score = `alpha * dense + (1 - alpha) * sparse`
- **Configurable params**: `fusion_mode` (rrf|weighted), `k_dense` (1-100), `k_sparse` (1-100), `alpha` (0-1) exposed on all retrieve functions
- **RRF k=60**: `_RRF_K` constant set to 60 (was implicit default, now documented)
- **`_FETCH_N` removed**: replaced by `k_dense`/`k_sparse` params per retrieval path
- **Fallback**: pure vector search when BM25 fails or query is empty
- **Params exposed** on file search API: `?fusion_mode=&k_dense=&k_sparse=&alpha=`

### Key files
| File | Change |
|------|--------|
| `backend/llm/retriever.py` | `_weighted_merge()`, `_RRF_K=60`, fusion params on all 4 retrieve functions |
| `backend/api/files/router.py` | search route passes fusion params |

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
