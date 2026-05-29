# Known Bugs & Issues

Tracker for all confirmed bugs across the stack. Check off when fixed.

Legend: `[x]` = fixed · `[~]` = partially fixed · `[ ]` = open

---

## NIM / LLM Resilience

- [x] **NIM retry exhausts too fast on transient spikes**
  - **Subdir:** `backend/`
  - **Files:** `llm/nim.py:130`, `config.py:46`
  - **Fix:** Backoff changed to `min(30, 2**attempt) * (0.75 + 0.5*random)`. `MAX_RETRIES` default raised from `2` → `3` (4 total attempts).

- [x] **Circuit breaker threshold too low — trips on brief blips**
  - **Subdir:** `backend/`
  - **Files:** `llm/circuit_breaker.py:10–11`
  - **Fix:** `_THRESHOLD=5`, `_COOLDOWN=90`.

- [x] **Circuit breaker state lost on container restart**
  - **Subdir:** `backend/`
  - **Files:** `llm/circuit_breaker.py:68–81`, `main.py:53–54`
  - **Fix:** Redis-backed persistence via `cb:open:{model}` keys. `restore_circuit_state()` called on startup. Gated on `USE_REDIS`.

- [x] **No startup model health probe — dead models get real traffic first**
  - **Subdir:** `backend/`
  - **Files:** `main.py:70–71`, `api/system.py`
  - **Fix:** `probe_models_on_startup()` called in lifespan. Pre-trips circuit for failing models.

- [x] **Partial stream failure counted as full request failure**
  - **Subdir:** `backend/`
  - **Files:** `api/chat/stream.py:293`, `api/chat/stream.py:303`
  - **Fix:** Mid-stream breaks now set `status="partial"` instead of `"error"`.

- [x] **Rate limiter fails open on Redis outage with no warning**
  - **Subdir:** `backend/`
  - **Files:** `rate_limiter/rate_limiter.py:144`, `:199`, `:255`, `:273`
  - **Fix:** Warnings logged on every fail-open activation with scope and key.

- [x] **No dedicated "all models failed" Prometheus counter**
  - **Subdir:** `backend/`
  - **Files:** `observability/prom_metrics.py:80–82`, `api/chat/stream.py:298`
  - **Fix:** `ALL_MODELS_FAILED` counter added and incremented on chain exhaustion.

---

## Graph Memory / Neo4j

- [x] **Graph extraction uses 8B model — unreliable structured JSON output**
  - **Subdir:** `backend/`
  - **Files:** `llm/graph_memory.py:82`
  - **Fix:** Switched to `MODELS["reasoning"]` (70B).

- [x] **No entity name length limit — oversized names enter Neo4j**
  - **Subdir:** `backend/`
  - **Files:** `llm/graph_memory.py:13`, `:107`
  - **Fix:** `_MAX_ENTITY_NAME_LEN=200` enforced in entity batch filter.

- [x] **No per-call entity/relationship count cap**
  - **Subdir:** `backend/`
  - **Files:** `llm/graph_memory.py:14–15`, `:110`, `:122`
  - **Fix:** `_MAX_ENTITIES_PER_CALL=30`, `_MAX_RELS_PER_CALL=60`.

- [x] **MERGE...SET unconditionally overwrites entity type**
  - **Subdir:** `backend/`
  - **Files:** `llm/graph_memory.py:152`
  - **Fix:** `CASE WHEN e.type <> 'OTHER' THEN e.type ELSE n.type END` — only overwrites with a more specific type.

- [x] **No Redis cache invalidation after graph write**
  - **Subdir:** `backend/`
  - **Files:** `llm/graph_memory.py:42–50`, `:156`
  - **Fix:** `_cache_del_user(user_id)` deletes all `graph:{user_id}:*` keys via `scan_iter` after a successful write.

- [x] **No per-user graph size limit — unbounded Neo4j growth**
  - **Subdir:** `backend/`
  - **Files:** `llm/graph_memory.py:16`, `:140`
  - **Fix:** `_MAX_USER_ENTITIES=500`. Oldest nodes replaced when limit is exceeded.

- [x] **No graph validate/prune endpoint**
  - **Subdir:** `backend/`
  - **Files:** `api/graph.py:97–121`
  - **Fix:** `POST /graph/prune` — deletes oversized/stale `OTHER`-typed entities.

- [x] **Graph extraction background task runs without compaction coordination**
  - **Subdir:** `backend/`
  - **Files:** `llm/graph_memory.py:126–127`, `llm/summarizer/compact.py:21`
  - **Fix:** `compact_memory()` sets `compact:running:{user_id}` Redis key. `extract_and_store()` skips if key present.

---

## Memory System (Postgres)

- [x] **MemoryConflict suppression is permanent — facts disappear silently**
  - **Subdir:** `backend/`
  - **Files:** `models/user.py:64`, `api/memory.py:144`, `:305`, `:313`
  - **Fix:** `expires_at` column added. New conflicts get a 7-day expiry. Expired conflicts excluded from suppression queries.

- [x] **`fact_saliences` JSONB grows unboundedly**
  - **Subdir:** `backend/`
  - **Files:** `llm/summarizer/salience.py:46–52`
  - **Fix:** `decay_fact_saliences()` drops entries where decayed score < 0.05 on every compaction cycle.

- [x] **Salience decays only on compaction — stale facts persist across sessions**
  - **Subdir:** `backend/`
  - **Files:** `api/chat/helpers.py:124–130`
  - **Fix:** Time-based decay applied in-memory during context injection: `0.95 ** (hours_since_compaction / 24)` multiplied against ranking saliences before fact sorting. Not written back to DB.

---

## Request Handling

- [x] **Auto-title can fire twice on concurrent messages**
  - **Subdir:** `backend/`
  - **Files:** `api/chat/background.py:45–66`
  - **Fix:** Replaced read-then-write with an atomic `UPDATE ... WHERE id = :conv_id AND title = :default` via SQLAlchemy `update()`. If two tasks race, only one matches the WHERE clause — the second silently affects 0 rows.

- [x] **Graph cache key uses SHA256[:20] — theoretical collision**
  - **Subdir:** `backend/`
  - **Files:** `llm/graph_memory.py:20`
  - **Fix:** Extended to `hexdigest()[:32]` (128-bit key space).

---

## Background Jobs (ARQ)

- [x] **ARQ jobs silently dropped after 4 failed attempts**
  - **Subdir:** `backend/`
  - **Files:** `observability/prom_metrics.py:85–88`, `services/arq_worker.py:30`, `:74`, `:110`, `:123`
  - **Fix:** `ARQ_JOB_FAILED = Counter("arq_job_failed_total", ..., ["job_type"])` added. All four job types (`process_file`, `generate_insight`, `re_embed_batch`, `compact_memory`) increment it on permanent failure. File jobs also set `upload_status="error"`.

---

## Observability / Grafana

- [ ] **model_usage, api_errors, model_latency, ai_request_latency panels show no data**
  - **Subdir:** `docker/`
  - **Files:** `docker/grafana/provisioning/dashboards/nim-gateway.json`
  - **Status:** PromQL expressions match backend exports. Likely a testing artifact — panels were empty because NIM models were down during testing, so `MODEL_USAGE.inc()` never fired (gated on `status=="success" and model_used!="unknown"`). Verify by running `curl localhost:8000/metrics | grep model_usage` after a successful chat. If the counter appears, panels are correct and this bug can be closed.

- [x] **Prometheus counters reset on container restart — rate panels lose history**
  - **Subdir:** `backend/`, `docker/`
  - **Files:** `docker/docker-compose.yml:24`, `backend/observability/prom_metrics.py:96–99`
  - **Fix:** `PROMETHEUS_MULTIPROC_DIR: /tmp/prom_multiproc` set in compose. `prom_metrics.py` uses `MultiProcessCollector` when env var is present. `prometheusdata` named volume persists Prometheus TSDB across restarts. Rate-based panels (`rate()`) handle counter resets natively.

- [x] **No Grafana alert on circuit breaker opening**
  - **Subdir:** `docker/`
  - **Files:** `docker/grafana/provisioning/alerting/nim-alerts.yml`
  - **Fix:** Unified alert rule `nim-circuit-breaker-alert` — fires when `rate(circuit_breaker_trips_total[5m]) > 0` sustained for 1 minute.

- [x] **No Grafana alert on success rate drop**
  - **Subdir:** `docker/`
  - **Files:** `docker/grafana/provisioning/alerting/nim-alerts.yml`
  - **Fix:** Unified alert rule `nim-success-rate-alert` — fires when success rate < 99% sustained for 1 minute.

---

## Data Integrity

- [x] **Pre-migration 011 messages have NULL token counts**
  - **Subdir:** `backend/`
  - **Files:** `alembic/versions/032_message_token_estimate.py`
  - **Fix:** Migration 032 adds `token_estimate` flag and backfills NULL-token assistant messages with character-based estimates.

---

## Compatibility

- [x] **passlib crypt warning on Python 3.13+**
  - **Subdir:** `backend/`
  - **Files:** `auth/security.py`
  - **Fix:** `passlib` replaced with direct `bcrypt` (`bcrypt.hashpw`, `bcrypt.checkpw`).

---

## Summary

| Area | Total | Fixed | Open |
|------|-------|-------|------|
| NIM / LLM Resilience | 7 | 7 | 0 |
| Graph Memory / Neo4j | 8 | 8 | 0 |
| Memory System (Postgres) | 3 | 3 | 0 |
| Request Handling | 2 | 2 | 0 |
| Background Jobs | 1 | 1 | 0 |
| Observability / Grafana | 4 | 3 | 1 |
| Data Integrity | 1 | 1 | 0 |
| Compatibility | 1 | 1 | 0 |
| **Total** | **27** | **26** | **1** |
