# Roadmap & History

Suggestions only — ask for specs before implementing any.

---

## Completed Features (backend)

### Reliability
- ARQ persistent task queue — `services/arq_worker.py` + `core/arq_pool.py`; inline fallback
- File processing retry — ARQ retries 3× at 5s/30s/120s; marks error on final failure
- DB in health check — `GET /health` includes `{db: {status, latency_ms}}` via SELECT 1

### Agency
- Proactive suggestions — `llm/agency.py`; llama 1-sentence hint; SSE `{type:"proactive"}` before done; max_tokens=35
- Background insight engine — `generate_insight_job` ARQ; every 10 asst msgs; max 3 unread per user
- Insights API — `GET /insights` · `PATCH /insights/{id}/read` · `DELETE /insights/{id}`

### Capabilities
- OpenAI-compatible endpoint — `POST /v1/chat/completions`; maps gpt-4→reasoning, gpt-3.5→llama; JWT or API key
- API key auth — `User.api_key` (migration 022); generate/revoke via `/auth/me/api-key`
- Standalone file search — `GET /files/search?q=&workspace_id=&top_k=`; hybrid RRF

### Cost / Performance
- Streaming response cache — v2 key = msg+model+history[-4]+sysprompt; bypassed only on file_chunks/image/params
- Per-model rate limits — llama=15, coder=10, reasoning=5 req/60s; explicit selection only

### Admin / Observability
- Admin audit log — `AdminAuditLog` (migration 024); `_audit()` helper; `GET /admin/audit-log`
- Rolling cost window — `cost_window_days` (migration 025); default 30 days; null=all-time

---

## Possible Next Features

### UX / Frontend
- Message editing — resend edited user message; truncate conv to that point
- Drag-and-drop upload
- Keyboard shortcuts — Ctrl+Enter send, Ctrl+K search, Esc close panels
- Mobile layout — sidebar hamburger, stacked input
- Admin frontend panel — user table + usage + enable/disable (currently API-only)

### RAG / Memory
- Re-embed on MODEL_EMBEDDING change — old chunks become stale
- Per-conversation memory — separate sheet per conv
- Graph memory — entities + relationships

### Token / Cost
- Budget dashboard — Grafana per-user panels
- Monthly rollup aggregate table
- User-configurable cost alerts

### Observability / Admin
- User activity timeline — last N messages per user with timestamps + models
- Memory system metrics — Prometheus counters for memory updates, RAG hits
- Grafana alerts — error rate >5%, latency p95 >10s, cost spike
- Usage CSV export — `GET /admin/export/usage.csv`

### Infrastructure
- Prometheus remote write — persist metrics across restarts
- Automated backup verification — weekly restore test

### Security (low priority — home/LAN deployed)
- Prompt injection detection — heuristic before passing to model
- CORS lockdown — restrict to known frontend origin in production

---

## Migration History
| # | File | What |
|---|------|------|
| 001–007 | — | conversations, memory, embeddings, project summary, versioning, model control |
| 008 | file_knowledge.py | file_chunks vector(1024) + HNSW + conversation_files |
| 009 | file_versions.py | file_versions table |
| 010 | tool_call_log.py | tool_call_logs (id, user_id, conv_id, tool_name, args JSONB, result_preview) |
| 011 | token_usage.py | prompt_tokens, completion_tokens, total_tokens, cost_usd on messages |
| 012 | cost_caps.py | cost_limit_usd (Float, nullable) on users |
| 013 | hybrid_search.py | pg_trgm; content_tsv GENERATED + GIN on file_chunks |
| 014 | prompt_templates.py | prompt_templates table |
| 015 | scheduled_prompts.py | scheduled_prompts + scheduled_prompt_runs |
| 016 | file_dedup.py | sha256_hash + ix_files_user_sha256 on files |
| 017 | bm25_simple_config.py | recreates content_tsv with 'simple' config on file_chunks + message_embeddings |
| 018 | workspaces.py | workspaces table; files.workspace_id String→UUID FK; conversations.workspace_id |
| 019 | workspace_memory.py | workspace_memory table (1:1 with workspaces) |
| 020 | message_search.py | messages.content_tsv GENERATED tsvector + GIN |
| 021 | invitations.py | invitations (token, created_by, used_by, expires_at) |
| 022 | api_key.py | api_key (String 64, unique, nullable) + index on users |
| 023 | user_insights.py | user_insights table |
| 024 | admin_audit_log.py | admin_audit_logs (4 indexes) |
| 025 | cost_window.py | cost_window_days (Integer, nullable) on users |
