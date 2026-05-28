# HANDOFF ARCHIVE
Completed features — full detail. See Archive rules in root CLAUDE.md.

---

## Retrieval Eval Harness
**Completed:** 2026-05-28

### What was built
- **`debug: bool = False` param** on `retrieve()` / `retrieve_from_files()` in `retriever.py` — when `True`, returns `(chunks, debug_info)` tuple; debug_info per hit: `{chunk_id, source_id, score, rank, fusion_mode}`. Default `False` → unchanged `list[dict]`. Zero changes to existing call sites.
- **`?debug=true` on file search API** (`search.py`) — returns `{"results": [...], "debug": [...]}` with per-hit `{chunk_id, file_id, filename, score, rank, fusion_mode}`. Default off → unchanged response.
- **Eval harness** (`tests/retrieval/test_hybrid_eval.py`) — 26 tests covering 5 query types (exact_match, fuzzy_bm25_boost, multi_source, vector_only_fallback, single_source) × 4 fusion modes (rrf k=60, weighted alpha=0.3/0.5/0.7) + 2 file types × 2 modes + debug flag checks. Computes recall@3 (≥0.7), MRR (≥0.6), citation coverage (≥0.8). No live NIM — mocks `db.execute()` via `AsyncMock`.

### Key files
| File | Change |
|------|--------|
| `backend/tests/retrieval/test_hybrid_eval.py` | 26 eval tests with fixed dataset, metrics, baselines |
| `backend/llm/retriever.py` | `debug` param on `retrieve()` and `retrieve_from_files()` |
| `backend/api/files/search.py` | `?debug=true` query param on search endpoint |

---

## Neo4j Grounding Injection
**Completed:** 2026-05-28

### What was built
- **`get_health()`** in `core/neo4j_client.py` — returns `{"available": bool, "entity_count": int, "relation_count": int}`; runs `MATCH (e:Entity) RETURN count(e)` and `MATCH ()-[r:RELATED_TO]->() RETURN count(r)`
- **`query_by_keywords()`** in `llm/graph_memory.py` — extracts keywords (> 2 chars, strips stopwords from `_STOPWORDS` set), runs fulltext entity search, expands neighborhood per matched entity via `(e)-[r:RELATED_TO]->(other)`, returns formatted `[GRAPH FACTS]` block with `Entity --[RELATION]→ Entity` lines
- **`[GRAPH FACTS]` injection** in `context.py` — new `graph_facts: str = ""` param on `build_context_messages()`; injected after `[GRAPH CONTEXT]`, before `[USER STATE]`; context budget tier merged with `[GRAPH CONTEXT]` under same priority (tier 4)
- **`_build_stream_context()`** in `helpers.py` — calls `query_by_keywords(user_id, req.message)` after existing `graph_context` query, stores in dict as `graph_facts`
- **`GET /graph/health`** — returns `get_health()` result (Neo4j connectivity + global entity/relation counts)
- **`GET /graph/sample`** — returns up to 10 random `{source, relation, target}` triples for current user via `MATCH (a)-[r:RELATED_TO]->(b) RETURN ... LIMIT 10`

### Key files
| File | Change |
|------|--------|
| `backend/core/neo4j_client.py` | `get_health()` function |
| `backend/llm/graph_memory.py` | `query_by_keywords()` with stopword filtering, fulltext lookup, neighborhood expansion |
| `backend/llm/service/context.py` | `graph_facts` param, `[GRAPH FACTS]` injection block, budget tier |
| `backend/api/chat/helpers.py` | `query_by_keywords()` call in `_build_stream_context()` |
| `backend/api/chat/router.py` | passes `graph_facts` to `generate_stream()` |
| `backend/api/graph.py` | `GET /graph/health`, `GET /graph/sample` endpoints |
| `backend/llm/service/stream.py` | forwards `graph_facts` to `build_context_messages()` |

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
