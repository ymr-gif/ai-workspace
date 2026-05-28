You AI. You think clear. You speak short.

Rules:
- No fluff words.
- No long sentences.
- No repetition.
- No greetings unless asked.
- No explanation unless asked.
- Prefer short phrases over full sentences.
- Remove filler words (the, very, just, actually, basically).

Style:
- Use simple subject-verb-object.
- Break long ideas into steps.
- Use bullets when possible.
- Prefer commands over explanations.
- Example: "You should validate input" → "Validate input"

Behavior:
- If user ask, answer direct.
- If user want plan, give steps only.
- If unclear, ask short question.

Goal:
- Save tokens.
- Max meaning, min words.

For every change:
- list every modified file
- explain what changed
- show diffs or full contents
- do not omit helper/config/import changes

---

# Project Reference — NIM AI Gateway

## What This Is
FastAPI backend routing chat messages to NVIDIA NIM models via keyword classification.
React/Vite frontend. Docker Compose stack: Postgres + pgvector, Redis, Prometheus, Grafana.
Features: SSE streaming, conversation history, multi-tier memory, pgvector RAG, file knowledge base, AI agent tool loop, model control, markdown rendering, **workspace layer** (conversations + files scoped to workspaces), invite-gated registration, conversation search + export, auto-title.

> Subdir details: `backend/CLAUDE.md` · `docker/CLAUDE.md` · `frontend/CLAUDE.md`
> Completed plan (workspace layer, invites, search, export, auto-title): `~/.claude/plans/since-we-are-in-smooth-lobster.md`

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

## Reliability
| Setting | Value | Location |
|---------|-------|----------|
| Circuit breaker threshold | 3 failures | `llm/circuit_breaker.py` |
| Circuit breaker cooldown | 30s | `llm/circuit_breaker.py` |
| Request timeout | 30s | `REQUEST_TIMEOUT` env |
| Max concurrent requests | 10 (cap 50) | `MAX_CONCURRENT_REQUESTS` env |
| Rate limit (chat) | 15 req / 60s per user (global) | `api/chat/router.py` |
| Rate limit (per-model) | llama=15, coder=10, reasoning=5 req/60s — explicit selection only | `rate_limiter/rate_limiter.py:check_model_rate` |
| Rate limit (upload) | 20 req / 60s per user | `api/files/router.py` |
| Rate limit (ingest-url) | 10 req / 60s per user | `api/files/ingest.py` |
| Cache bypass | model_params / file_chunks / image_b64 (history+model+sysprompt now in key) | `llm/service/stream.py` |
| Embedding timeout | 15s | `llm/embeddings.py` |
| Memory write lock | pg_advisory_xact_lock(user_id) | `summarizer.py` |
| Max tool iterations | 10 | `llm/service/stream.py` |
| Tool repetition guard | >3 calls same tool → abort | `llm/service/stream.py` |
| Tool keyword gate | `_needs_file_tools(message)` | `llm/service/context.py` |
| Max file read (tool) | 100,000 chars | `llm/tools.py` |

---

## Known Issues
- No integration tests — `/chat` not covered without live NIM API
- `passlib` deprecation warning for `crypt` on Python 3.13+ — harmless on 3.11
- Embedding latency (~100-300ms) adds to stream start time
- File RAG requires explicit attachment (Library → + button); upload alone is not enough
- `_needs_file_tools` keyword-based — may miss implicit file requests ("look at my notes")
- Token counts on pre-migration 011 messages are NULL
- Token pricing hardcoded in `config.py:MODEL_PRICING` — verify at build.nvidia.com/explore/llm
- Processing progress shows 0.0 briefly before first chunk embeds
- DOCX table extraction appends tables after all paragraphs (not interleaved)
- Prometheus counters reset on container restart — rate panels lose history; stat panels (PostgreSQL) unaffected
- `$ Usage` panel shows current user only; admin must use `/admin/users` API directly
- Cost cap supports rolling window via `cost_window_days` (default 30); set to null for all-time

---

## Seeded Users
| Username | Password | Role |
|----------|----------|------|
| admin | admin-secret | admin |
| user | user-secret | user |

---

## Quick Commands
```bash
# Start everything
cd docker && docker compose up -d

# Production deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Backup DB
./docker/backup.sh
# Restore: gunzip -c <file>.sql.gz | docker compose exec -T postgres psql -U scylla nimrouter

# Rebuild after backend changes
docker compose build --no-cache api && docker compose up -d api

# Rebuild frontend
docker compose build --no-cache frontend && docker compose up -d frontend

# Rebuild both
docker compose build --no-cache api frontend && docker compose up -d api frontend

# Full reset (wipes DB)
docker compose down -v --remove-orphans && docker compose up -d --build

# Run migration
docker compose exec api sh -c "cd /app/backend && alembic upgrade head"

# Seed users
docker compose exec api python create_user.py

# Run tests
cd backend && python -m pytest tests/test.py -v
```

---

## HANDOFF Protocol

Root is coordinator. One physical `HANDOFF.md` exists in the repo at any time. Its location = current owner.

**Locate file first:**
```bash
find . -name HANDOFF.md
```

**Starting a feature:**
1. Find HANDOFF.md (may be at root or in a subdir)
2. Amend: set Active Feature, write task lists per agent, set execution order
3. `mv HANDOFF.md backend/HANDOFF.md` (or whichever dir executes first)
4. Append a History row

**Returning to in-flight feature:**
1. Find file → read Recorded sections from prior agents
2. Amend next agent's task list if new addenda needed
3. Leave file in place (do not move — the owning agent moves it when done)

**Task format:** one checkbox = one concrete action (small and specific)

**Execution order options:** `backdir → frontdir → dockdir` · adjust per feature · skip unused dirs · return to root when all done (set status: done)
