# Project Reference — NIM AI Gateway

## What This Is
FastAPI backend routing chat messages to NVIDIA NIM models via keyword classification.
React/Vite frontend. Docker Compose stack: Postgres + pgvector, Redis, Neo4j, Prometheus, Grafana.
Features: SSE streaming, conversation history, multi-tier memory, pgvector RAG, file knowledge base, AI agent tool loop, model control, markdown rendering, workspace layer, invite-gated registration, conversation search + export, auto-title, graph memory (Neo4j), re-embed on MODEL_EMBEDDING change, retrieval eval harness (`tests/retrieval/test_hybrid_eval.py`), memory salience engine, context budget allocator, memory compaction, adaptive retrieval policy.

> Subdir details: `backend/CLAUDE.md` · `docker/CLAUDE.md` · `frontend/CLAUDE.md`
> Commands: `COMMANDS.md` · HANDOFF workflow: `HANDOFF_PROTOCOL.md`

---

## Repo Layout
```
ai-api/
├── .env                  ← secrets (gitignored) — root, loaded by find_dotenv()
├── .env.example          ← all supported vars documented
├── backend/              ← FastAPI app (see backend/CLAUDE.md)
├── docker/               ← Compose, Dockerfiles, Grafana (see docker/CLAUDE.md)
└── frontend/             ← React/Vite UI (see frontend/CLAUDE.md)
```

---

## Model Routing

### Active Models (verified 2026-05-24)
| Role | Model | Env Var |
|------|-------|---------|
| llama | `meta/llama-3.1-8b-instruct` | `MODEL_LLAMA` |
| coder | `deepseek-ai/deepseek-v4-flash` | `MODEL_CODER` |
| reasoning | `meta/llama-3.3-70b-instruct` | `MODEL_REASONING` |
| embedding | `nvidia/nv-embedqa-e5-v5` (1024d) | `MODEL_EMBEDDING` |

### Dead Models (do not use)
- `qwen/qwen2.5-coder-32b-instruct` — EOL 2026-05-12 (410)
- `mistralai/codestral-22b-instruct-v0.1` — 404
- `meta/codellama-70b`, `nvidia/llama-3.1-nemotron-70b-instruct` — 404
- `ibm/granite-*`, `google/codegemma-*`, `deepseek-ai/deepseek-coder-*` — 404

### Selection Priority
`per-request model_override > conversation locked_model > keyword router (auto)`

### Fallback Chain
`chosen model → reasoning → coder → llama`

---

## Non-obvious Reliability Settings
| Setting | Value |
|---------|-------|
| Circuit breaker | 3 failures → open; 30s cooldown |
| Request timeout | `REQUEST_TIMEOUT` env (default 30s) |
| Max concurrent | `MAX_CONCURRENT_REQUESTS` env (default 10, cap 50) |
| Rate limit (chat) | 15 req / 60s per user |
| Rate limit (per-model) | llama=15, coder=10, reasoning=5 req/60s — explicit selection only |
| Cache bypass | triggered by: file_chunks / image_b64 / model_params present |
| Memory write lock | `pg_advisory_xact_lock(user_id)` — prevents version races |
| Tool loop guard | max 10 iterations; >3 same tool → abort |

---

## Known Issues
- No chat integration tests — `/chat` requires live NIM API; retrieval is covered by `tests/retrieval/test_hybrid_eval.py` (26 tests, mocked DB)
- `passlib` crypt warning on Python 3.13+ — harmless on 3.11
- File RAG requires explicit attachment (Library → + button); upload alone is not enough
- `_needs_file_tools` is keyword-based — may miss implicit file requests
- Token counts on pre-migration 011 messages are NULL
- Prometheus counters reset on container restart — rate panels lose history

---

## Seeded Users
| Username | Password | Role |
|----------|----------|------|
| admin | admin-secret | admin |
| user | user-secret | user |

---

## HANDOFF Protocol

### Roles
- **Root** — overseer/administrator. Plans, writes task lists, moves HANDOFF.md, manages archive, handles root-level escalations. **Does not implement code.** Exception: very minor tweaks (single-line values, typo fixes) that don't belong to any subdir.
- **`backend/`** — worker. Implements backend tasks only.
- **`frontend/`** — worker. Implements frontend tasks only.
- **`docker/`** — worker. Implements infra/compose tasks only.

Workers do not plan. Root does not implement — it delegates.

### Root-owned files (workers must not edit)
`.env` · `.env.example` · `.gitignore` · `.dockerignore` · `CLAUDE.md` (root) · `README.md` · `ROADMAP.md`

If a worker needs a root file changed: set `status: needs-root` in HANDOFF.md and pass back.

> Full workflow: see `HANDOFF_PROTOCOL.md`
