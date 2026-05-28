# HANDOFF ARCHIVE
Completed features — key design decisions and non-obvious implementation details.
Full code detail is in CLAUDE.md and git history.

---

## Autonomous Memory Writing
**Completed:** 2026-05-29

- **Tool**: `write_memory(fact: str)` — always available when `memory_enabled=True`
- **Flow**: tool call → executor returns `__CONFIRM_WRITE_MEMORY__:{fact}` sentinel → stream yields `{type:"confirm_write_memory", fact}` + `{type:"done"}` → generator returns (stream pauses, like ask_user)
- **API**: `POST /memory/write` — appends fact as new line (trim 500 chars), snapshots to `UserMemoryVersion`, bumps `version +1`, boosts `salience +0.1`
- **Frontend**: `pendingWriteFact` in `useConversations`; green card (bg `rgba(52,211,153,0.08)`, border `rgba(52,211,153,0.25)`); cleared on Accept (calls API), Dismiss, or next send

**Key files:** `llm/tools/schemas.py` · `llm/tools/executor.py` · `llm/service/stream.py` · `api/memory.py` · `hooks/useConversations.js` · `chat/MessageList.jsx`

---

## Memory Conflict Resolver
**Completed:** 2026-05-28

- **Model**: `MemoryConflict` — `id` (UUID PK), `user_id` FK, `fact_a`, `fact_b`, `conflict_type` (contradiction|duplicate|ambiguous), `resolution` (keep_a|keep_b|merge|discard_both|unresolved)
- **Detection**: pairwise LLM (llama) check post-compaction; skips `"none"` pairs
- **Suppression**: unresolved conflicts filtered from `[USER STATE]` injection at context build time
- **Resolution**: `POST /memory/conflicts/{id}/resolve` applies patch to `UserMemory.content`, bumps version
- **Migration**: 028

**Key files:** `models/user.py` · `alembic/028_memory_conflicts.py` · `llm/summarizer/conflicts.py` · `llm/service/context.py` · `api/memory.py`

---

## Adaptive Retrieval Policy
**Completed:** 2026-05-28

- **Classifier**: `classify_query(msg)` in `router.py` → `factual|relational|temporal|broad`; keyword-set matching, fallback `factual`
- **Policy map** in `retriever/policy.py`:
  - `factual` → weighted, alpha=0.7, top_k=5
  - `relational` → RRF, top_k=8, use_graph=true
  - `temporal` → RRF, k_sparse=10, top_k=6
  - `broad` → weighted, alpha=0.3, top_k=3
- Applied per-request in `_build_stream_context()`; logged with query_type + params

**Key files:** `llm/router.py` · `llm/retriever/policy.py` · `api/chat/helpers.py`

---

## Salience Integration Completion
**Completed:** 2026-05-28

- **Per-fact salience**: `UserMemory.fact_saliences` JSONB maps fact text → score (default 1.0)
- **Injection**: facts sorted high→low before `[USER STATE]` (top 20); bumped per-access via `bump_fact_saliences()`
- **Budget**: tier-1 partial drop removes low-salience facts (< 0.5) before dropping entire `[USER STATE]` block
- **Decay**: per compaction cycle; facts < 0.3 dropped from saliences map
- **Retrieval re-rank**: `final_score * (1 + memory_salience * 0.05)`
- **Migration**: 029

**Key files:** `models/user.py` · `llm/summarizer/salience.py` · `api/chat/helpers.py` · `llm/service/context.py`

---

## Memory Salience Engine
**Completed:** 2026-05-28

- **Fields on `UserMemory`**: `salience` (float, default 1.0), `confidence` (float, default 1.0), `last_used_at`
- **`compute_salience()`**: recency decay (exponential 0.05) + frequency cap (+10%/access), clamped [0,2]
- **Compaction**: decays ×0.95/cycle; clears memory entirely if salience < 0.3
- **Read-time**: bumped on every context load; `POST /memory/decay` for manual pass
- **Migration**: 027

**Key files:** `models/user.py` · `llm/summarizer/salience.py` · `llm/summarizer/compact.py` · `api/memory.py`

---

## Memory Compaction Job
**Completed:** 2026-05-28

- **`compact_memory()`**: `pg_advisory_xact_lock(user_id)` → skips if < 100 words → LLM (llama) dedup/compress → cap 500 words → snapshot to `UserMemoryVersion`
- **ARQ job**: `compact_memory_job` — queued via pool; `max_tries=4`
- **Cron**: daily 3 AM UTC via APScheduler in `scheduler_worker.py`
- **API**: `POST /memory/compact` → enqueues ARQ job

**Key files:** `llm/summarizer/compact.py` · `services/arq_worker.py` · `services/scheduler_worker.py` · `api/memory.py`

---

## Re-embed on MODEL_EMBEDDING Change + Graph Memory
**Completed:** 2026-05-28

- **Re-embed**: startup compares `MODEL_EMBEDDING` env vs `system_config` DB row; queues ARQ batches of 100 on mismatch; `POST /admin/re-embed` for manual trigger
- **Neo4j**: async driver; fails open if `NEO4J_PASSWORD` unset; constraint `(user_id, name)` unique + fulltext index `entity_name_ft` + range index `entity_user_id` created at startup
- **Graph writes**: `extract_and_store()` fires post-reply; UNWIND batch (2 round-trips); entity + relation per user
- **Graph context**: `[GRAPH CONTEXT]` injected when memory enabled; `[GRAPH FACTS]` from `query_by_keywords()`; both cached in Redis 60s
- **`query_graph` tool**: available in agent loop
- **Migration**: 026 (`system_config` table)
- **Env vars**: `NEO4J_URI` (bolt://neo4j:7687) · `NEO4J_USER` (neo4j) · `NEO4J_PASSWORD` (required to enable)
- **Driver**: `max_connection_pool_size=20`, `connection_timeout=5s`

**Key files:** `core/neo4j_client.py` · `llm/graph_memory.py` · `services/re_embed.py` · `api/graph.py` · `alembic/026_system_config.py`
