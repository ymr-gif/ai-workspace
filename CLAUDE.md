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
FastAPI backend that routes chat messages to NVIDIA NIM models based on keyword classification.
React/Vite frontend. Full Docker Compose stack with Postgres, Redis, Prometheus, Grafana.

---

## Repo Structure
```
ai-api/
├── .env                        ← secrets (gitignored) — root, loaded by find_dotenv()
├── .env.example                ← all supported vars documented
├── .gitignore / .dockerignore
├── backend/
│   ├── main.py                 ← FastAPI app, all routes, lifespan
│   ├── config.py               ← all env vars, startup guards, _int_env() helper
│   ├── models.py               ← SQLAlchemy ORM: User, File, FileChunk
│   ├── create_user.py          ← seeds admin/user accounts
│   ├── alembic.ini             ← migrations config (script_location=%(here)s/alembic)
│   ├── requirements.txt        ← 42 lines, all unused bloat removed
│   ├── auth/
│   │   ├── router.py           ← /auth/token, /register, /me endpoints
│   │   ├── security.py         ← JWT, bcrypt, get_current_user, require_role
│   │   ├── schemas.py          ← Token, TokenData, RegisterRequest pydantic models
│   │   └── __init__.py         ← re-exports: auth_router, get_current_user, require_role
│   ├── llm/
│   │   ├── service.py          ← thin orchestrator: cache → route → call → fallback
│   │   ├── nim.py              ← HTTP call to NIM API, error handling
│   │   ├── router.py           ← classify() keyword matching, route()
│   │   ├── circuit_breaker.py  ← is_open(), record_failure(), record_success()
│   │   ├── client.py           ← shared httpx.AsyncClient + semaphore
│   │   └── __init__.py
│   ├── cache/
│   │   ├── cache.py            ← Redis primary + in-memory LRU fallback
│   │   ├── keys.py             ← normalize(), make_key() → SHA256 hex
│   │   ├── memory.py           ← OrderedDict LRU, max 1000 entries
│   │   └── __init__.py         ← re-exports: get_cached_response, set_cached_response
│   ├── core/
│   │   ├── db.py               ← async SQLAlchemy engine, get_db, init_db
│   │   ├── redis_client.py     ← singleton async Redis, init_redis(), get_redis()
│   │   ├── logger.py           ← setup_logging(), JSON or plain formatter by LOG_FORMAT
│   │   └── __init__.py
│   ├── rate_limiter/
│   │   ├── rate_limiter.py     ← Redis sliding-window, fail-open
│   │   └── __init__.py         ← re-exports: limit
│   ├── observability/
│   │   ├── prom_metrics.py     ← all Prometheus counters/histograms defined here
│   │   ├── metrics.py          ← record_* wrappers, Prometheus inc/observe calls
│   │   ├── metrics_api.py      ← reads live from Prometheus objects (no aggregator)
│   │   ├── metrics_worker.py   ← standalone worker process (runs in own container)
│   │   ├── stream.py           ← emit() fire-and-forget Redis Stream writer
│   │   ├── observability.py    ← publish_request_event(), publish_error_event()
│   │   └── events.py           ← request_event(), error_event() dict builders
│   ├── api/
│   │   └── files.py            ← /files/upload (async, Depends(get_current_user))
│   ├── services/               ← empty package (chunker/embeddings deleted)
│   ├── storage/
│   │   └── storage_manager.py  ← async aiofiles, STORAGE_DIR from config
│   └── tests/
│       ├── test.py             ← 21 pytest unit tests (router, cache, auth, circuit)
│       └── model-list.py       ← lists all NIM models for this account
├── docker/
│   ├── docker-compose.yml      ← all services, build context is ..
│   ├── backend.Dockerfile      ← python:3.11-slim, WORKDIR /app/backend
│   ├── frontend.Dockerfile     ← node:20-alpine builder → nginx:alpine
│   ├── nginx.conf              ← reverse proxy: / → frontend, /api/ → api
│   ├── nginx.frontend.conf     ← frontend container nginx: SPA + /api/ proxy
│   └── prometheus.yml          ← scrapes api:8000/metrics every 5s
└── frontend/
    ├── vite.config.js          ← dev proxy: /api → localhost:8000
    ├── src/App.jsx             ← login form, JWT in localStorage as nim_token
    └── src/components/Chat.jsx ← chat UI, model tag per bubble, auto-logout on 401
```

---

## API Routes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/chat` | JWT | Main chat — routes to NIM model |
| GET | `/health` | none | Returns ok + model keys |
| GET | `/metrics` | none | Prometheus text export |
| POST | `/auth/token` | none | Login → JWT (form-encoded) |
| POST | `/auth/register` | none | Register user (role=user) |
| GET | `/auth/me` | JWT | Current user info |
| POST | `/files/upload` | JWT | Upload file |
| GET | `/metrics/overview` | none | Redis Streams aggregated stats |
| GET | `/metrics/models` | none | Per-model breakdown |
| GET | `/metrics/latency` | none | Latency percentiles |
| GET | `/prometheus` | none | prometheus-fastapi-instrumentator |

---

## Model Routing

### Active Models (as of 2026-05-24, verified working on this account)
| Role | Model | Env Var |
|------|-------|---------|
| llama (fast/general) | `meta/llama-3.1-8b-instruct` | `MODEL_LLAMA` |
| coder | `deepseek-ai/deepseek-v4-flash` | `MODEL_CODER` |
| reasoning | `meta/llama-3.3-70b-instruct` | `MODEL_REASONING` |

### Dead Models (do not use)
- `qwen/qwen2.5-coder-32b-instruct` — EOL 2026-05-12 (410)
- `mistralai/codestral-22b-instruct-v0.1` — 404 on this account
- `meta/codellama-70b` — 404 on this account
- `nvidia/llama-3.1-nemotron-70b-instruct` — 404 on this account (despite being in catalog)
- `ibm/granite-*`, `google/codegemma-*`, `deepseek-ai/deepseek-coder-*` — all 404

### classify() Keywords (backend/llm/router.py)
- **coder**: `code, error, bug, fix, debug, function, class, implement, write a, script, program, algorithm, syntax, compile, refactor, import, library, api, sql, query, regex`
- **reasoning**: `why, explain, how does, how do, what is, what are, compare, difference, analyze, reason, cause, effect, theory, concept, understand, depth, detail`
- **llama**: everything else

### Fallback Chain
`chosen model → reasoning → coder → llama`

---

## Reliability
| Setting | Value | Config |
|---------|-------|--------|
| Circuit breaker threshold | 3 failures | `llm/circuit_breaker.py:_THRESHOLD` |
| Circuit breaker cooldown | 30s | `llm/circuit_breaker.py:_COOLDOWN` |
| Max retries per model | 2 | `MAX_RETRIES` in `.env` |
| Request timeout | 30s | `REQUEST_TIMEOUT` in `.env` |
| Max concurrent requests | 10 (cap 50) | `MAX_CONCURRENT_REQUESTS` in `.env` |
| Rate limit (chat) | 15 req / 60s per user | `main.py:limit(15, 60, "chat")` |
| Cache | Redis primary + LRU fallback | `cache/cache.py` |

---

## Prometheus Metrics
All defined in `observability/prom_metrics.py`:

| Metric | Type | Labels | Recorded in |
|--------|------|--------|-------------|
| `api_requests_total` | Counter | `status` | `main.py` finally |
| `api_errors_total` | Counter | `type` | `main.py` finally |
| `cache_hits_total` | Counter | — | `metrics.py:record_cache_hit()` |
| `cache_misses_total` | Counter | — | `metrics.py:record_cache_miss()` |
| `cache_writes_total` | Counter | — | `metrics.py:record_cache_write()` |
| `model_usage_total` | Counter | `model` | `main.py` finally (success only) |
| `model_latency_seconds` | Histogram | `model` | `main.py` finally (success only) |
| `request_latency_seconds` | Histogram | — | `main.py` finally |
| `ai_request_latency_seconds` | Histogram | — | `main.py` finally |
| `fallback_total` | Counter | — | NOT YET WIRED |
| `circuit_breaker_trips_total` | Counter | — | `metrics.py:record_circuit_trip()` |

> `fallback_total` is defined and exported but never incremented — known gap.

---

## Docker Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn |
| frontend | 3000 | nginx serving React build |
| postgres | 5432 | internal only |
| redis | 6379 | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s |
| grafana | 3001 | admin/admin, datasource: http://prometheus:9090 |
| metrics-worker | — | runs `python -m observability.metrics_worker` |

---

## Known Issues / Pending
- `metrics-worker` container: `python -m observability.metrics_worker` — confirm start command in `docker-compose.yml`
- No integration tests (only unit tests) — `/chat` endpoint not covered without a running NIM API
- `passlib` deprecation warning for `crypt` on Python 3.13+ — harmless on 3.11

## Fixed (session 2026-05-24)
- `fallback_total` now incremented in `service.py` via `metrics.record_fallback()`
- `model_usage_total`, `model_latency_seconds`, `ai_request_latency_seconds` wired in `main.py` finally block
- `JWT_EXPIRE_MINUTES=60 * 24 * 30` expression handled by `_int_env()` in `config.py`
- `/files/upload` now uses `Depends(get_current_user)` — tied to JWT user
- Deleted `services/embeddings.py` — no longer loads HuggingFace weights at startup
- `metrics_aggregator.py` deleted — was calling sync Redis on async client; `metrics_api.py` now reads directly from Prometheus objects
- `auth/auth.py` split into `router.py`, `security.py`, `schemas.py`
- `llm/service.py` split into `service.py`, `nim.py`, `router.py`, `circuit_breaker.py`, `client.py`
- `requirements.txt` trimmed from 141 → 42 lines (removed torch, cuda, nvidia, opentelemetry, streamlit, pandas, scipy, etc.)

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

# Run migrations
docker compose exec api alembic upgrade head

# Seed users
docker compose exec api python create_user.py

# Get token
curl -s -X POST http://localhost:8000/auth/token -d "username=admin&password=admin-secret"

# Test chat
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"write a function to sort a list"}'

# Full reset (wipes DB)
docker compose down -v --remove-orphans && docker compose up -d

# Load test
k6 run -e TOKEN=$TOKEN tests/load_test.js

# Check available NIM models for your account
source ../.env && curl -s https://integrate.api.nvidia.com/v1/models \
  -H "Authorization: Bearer $NVIDIA_API_KEY" | python3 -c \
  "import sys,json; [print(m['id']) for m in json.load(sys.stdin).get('data',[])]"
```

