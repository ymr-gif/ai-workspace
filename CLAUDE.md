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
Features: SSE streaming, conversation history, multi-tier memory system, pgvector RAG.

---

## Repo Structure
```
ai-api/
├── .env                        ← secrets (gitignored) — root, loaded by find_dotenv()
├── .env.example                ← all supported vars documented
├── backend/
│   ├── main.py                 ← FastAPI app, all routes, lifespan, _estimate_tokens()
│   ├── config.py               ← env vars, startup guards, _int_env(); MODEL_EMBEDDING, NIM_EMBEDDING_URL
│   ├── models.py               ← ORM: User, File, FileChunk, Conversation, Message, UserMemory, MessageEmbedding
│   ├── create_user.py          ← seeds admin/user accounts
│   ├── alembic.ini
│   ├── requirements.txt        ← 43 lines (pgvector added)
│   ├── alembic/versions/
│   │   ├── 001_add_conversations.py      ← conversations + messages
│   │   ├── 002_add_user_memory.py        ← user_memory table
│   │   ├── 003_memory_improvements.py   ← history_summary + last_summarized_at
│   │   ├── 004_message_embeddings.py    ← message_embeddings + HNSW index (checkfirst)
│   │   └── 005_project_summary.py       ← project_summary column on user_memory
│   ├── auth/
│   │   ├── router.py           ← /auth/token, /register, /me
│   │   ├── security.py         ← JWT, bcrypt, get_current_user, require_role
│   │   ├── schemas.py          ← Token, TokenData, RegisterRequest
│   │   └── __init__.py         ← re-exports: auth_router, get_current_user, require_role
│   ├── llm/
│   │   ├── service.py          ← generate_stream(msg, history, memory, project, hist_summary, chunks, rid)
│   │   ├── nim.py              ← call() + call_stream() → NIM API
│   │   ├── router.py           ← classify() keyword matching, route()
│   │   ├── circuit_breaker.py  ← is_open(), record_failure(), record_success()
│   │   ├── client.py           ← shared httpx.AsyncClient + semaphore
│   │   ├── embeddings.py       ← embed(text, input_type) → list[float] via NIM embeddings API
│   │   ├── retriever.py        ← retrieve(), retrieve_global(), get_relevance_scores(),
│   │   │                          store_exchange(), is_reference_query()
│   │   ├── summarizer.py       ← update_memory(), compress_history(), update_project_summary()
│   │   └── __init__.py
│   ├── cache/
│   │   ├── cache.py            ← Redis primary + in-memory LRU fallback
│   │   ├── keys.py             ← normalize(), make_key() → SHA256 hex
│   │   ├── memory.py           ← OrderedDict LRU, max 1000 entries
│   │   └── __init__.py         ← re-exports: get_cached_response, set_cached_response
│   ├── core/
│   │   ├── db.py               ← engine, get_db, init_db (CREATE EXTENSION vector + checkfirst)
│   │   ├── redis_client.py     ← singleton async Redis, init_redis(), get_redis()
│   │   ├── logger.py           ← setup_logging(), JSON or plain formatter
│   │   └── __init__.py
│   ├── rate_limiter/
│   │   ├── rate_limiter.py     ← Redis sliding-window, fail-open
│   │   └── __init__.py         ← re-exports: limit
│   ├── observability/
│   │   ├── prom_metrics.py     ← all Prometheus counters/histograms
│   │   ├── metrics.py          ← record_* wrappers
│   │   ├── metrics_api.py      ← reads live from Prometheus objects
│   │   ├── metrics_worker.py   ← standalone worker (own container)
│   │   ├── stream.py           ← emit() Redis Stream writer
│   │   ├── observability.py    ← publish_request_event(), publish_error_event()
│   │   └── events.py           ← request_event(), error_event()
│   ├── api/
│   │   ├── files.py            ← /files/upload
│   │   ├── conversations.py    ← GET/DELETE /conversations, GET /conversations/{id}/messages
│   │   └── memory.py           ← GET /memory → {content, project_summary, version, updated_at}
│   ├── storage/
│   │   └── storage_manager.py
│   └── tests/
│       ├── test.py             ← 21 pytest unit tests
│       └── model-list.py
├── docker/
│   ├── docker-compose.yml      ← postgres: pgvector/pgvector:pg16
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── nginx.conf
│   ├── nginx.frontend.conf
│   ├── prometheus.yml
│   └── grafana/provisioning/   ← auto-loaded datasource + 10-panel dashboard
└── frontend/
    ├── vite.config.js
    ├── src/App.jsx             ← login form, JWT in localStorage as nim_token
    └── src/components/Chat.jsx ← sidebar + streaming chat + real-time memory panel
```

---

## API Routes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/chat` | JWT | Non-streaming chat |
| POST | `/chat/stream` | JWT | SSE streaming with conversation_id |
| GET | `/memory` | JWT | Returns memory sheet + project summary |
| GET | `/health` | none | ok + model keys |
| GET | `/metrics` | none | Prometheus export |
| POST | `/auth/token` | none | Login → JWT |
| POST | `/auth/register` | none | Register user |
| GET | `/auth/me` | JWT | Current user |
| POST | `/files/upload` | JWT | Upload file |
| GET | `/conversations` | JWT | List conversations |
| GET | `/conversations/{id}/messages` | JWT | Messages for conversation |
| DELETE | `/conversations/{id}` | JWT | Delete conversation |
| GET | `/metrics/overview` | none | Redis Streams stats |
| GET | `/metrics/models` | none | Per-model breakdown |
| GET | `/metrics/latency` | none | Latency percentiles |
| GET | `/prometheus` | none | prometheus-fastapi-instrumentator |

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

### Fallback Chain
`chosen model → reasoning → coder → llama`

---

## Memory System (full stack)

### Context Injection Order (`llm/service.py:generate_stream`)
```
1. [USER STATE]                    ← UserMemory.content (500w max, key:value)
2. [PROJECT STATE]                 ← UserMemory.project_summary (300w max, key:value)
3. [RELEVANT CONTEXT FROM EARLIER] ← top-K pgvector cosine results (MessageEmbedding)
4. [EARLIER IN THIS CONVERSATION]  ← Conversation.history_summary (200w max)
5. last 10 importance-weighted msgs ← scored 0.6×recency + 0.4×relevance
6. current user message
```

### Memory Sheet (`UserMemory.content`)
- Headers: `[USER] [STACK] [PROJECT] [CORRECTIONS] [PATTERNS]`
- Trigger: context >3000 estimated tokens OR every 10 assistant messages
- Background: `asyncio.create_task(update_memory(user_id, conv_id))`
- Reads all messages since `last_summarized_at`

### Project Summary (`UserMemory.project_summary`)
- Headers: `[GOALS] [ARCH] [STATUS] [PENDING]`
- Built from last 5 conversation `history_summary` values
- Trigger: context >4000 estimated tokens OR every 15 total messages
- Background: `asyncio.create_task(update_project_summary(user_id))`

### History Compression (`Conversation.history_summary`)
- Compresses `all_msgs[:-10]` → max 200 words
- Same trigger as project summary

### Retrieval-Augmented Memory (pgvector)
- `MessageEmbedding` table: one row per exchange (user+assistant pair)
- Embedding: `nvidia/nv-embedqa-e5-v5`, 1024d, `input_type=passage` for store / `query` for search
- Index: HNSW with `vector_cosine_ops` — O(log n) ANN search
- Normal queries: top_k=3 from current conversation
- Reference queries ("earlier", "remember", "you said"…): top_k=8
- If reference query returns nothing: `retrieve_global()` searches across ALL user conversations

### Importance Weighting
- Loads last 30 messages, scores each: `0.6 × recency + 0.4 × cosine_similarity`
- Keeps top 10, re-sorted chronologically

### Context-Pressure Trigger
- `_estimate_tokens(*texts)` = `sum(len(t) // 4)`
- compress + project: fires at >4000t OR fallback every 15 exchanges
- update_memory: fires at >3000t OR fallback every 10 assistant messages

### Frontend Memory Panel (`Chat.jsx`)
- "Memory" button in header — pulsing green dot while background tasks running
- Slides in from right, overlay closes on click
- Sections color-coded: USER/STACK/PROJECT/CORRECTIONS/PATTERNS + GOALS/ARCH/STATUS/PENDING
- "PROJECT STATE" divider separates two sheets
- Real-time polling: 2s × 15 after each response, 20s baseline while open
- Content-diff detection — green flash animation on change
- "updating…" text in header during post-response window

---

## Reliability
| Setting | Value | Config |
|---------|-------|--------|
| Circuit breaker threshold | 3 failures | `llm/circuit_breaker.py` |
| Circuit breaker cooldown | 30s | `llm/circuit_breaker.py` |
| Request timeout | 30s | `REQUEST_TIMEOUT` in `.env` |
| Max concurrent requests | 10 (cap 50) | `MAX_CONCURRENT_REQUESTS` in `.env` |
| Rate limit (chat) | 15 req / 60s per user | `main.py` |
| Cache | Redis primary + LRU fallback | `cache/cache.py` |
| Cache bypass | when history present | `service.py` |
| Embedding timeout | 15s | `llm/embeddings.py` |

---

## Prometheus Metrics
| Metric | Type | Labels | Recorded in |
|--------|------|--------|-------------|
| `api_requests_total` | Counter | `status` | `main.py` |
| `api_errors_total` | Counter | `type` | `main.py` |
| `cache_hits_total` | Counter | — | `cache.py` |
| `cache_misses_total` | Counter | — | `cache.py` |
| `cache_writes_total` | Counter | — | `cache.py` |
| `model_usage_total` | Counter | `model` | `main.py` |
| `model_latency_seconds` | Histogram | `model` | `main.py` |
| `request_latency_seconds` | Histogram | — | `main.py` |
| `ai_request_latency_seconds` | Histogram | — | `main.py` |
| `fallback_total` | Counter | — | `service.py` |
| `circuit_breaker_trips_total` | Counter | — | `metrics.py` |

---

## Docker Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn |
| frontend | 3000 | nginx serving React build |
| postgres | 5432 | `pgvector/pgvector:pg16` image |
| redis | 6379 | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s |
| grafana | 3001 | admin/admin, auto-provisioned dashboard |
| metrics-worker | — | `python -m observability.metrics_worker` |

---

## Known Issues / Pending
- No integration tests — `/chat` endpoint not covered without running NIM API
- `passlib` deprecation warning for `crypt` on Python 3.13+ — harmless on 3.11
- Embedding latency (~100-300ms) adds to request setup time before stream starts

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

# Full reset (required after postgres image change)
docker compose down -v --remove-orphans && docker compose up -d --build

# Migrations
docker compose exec api alembic upgrade head

# Seed users
docker compose exec api python create_user.py

# Get token
export TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -d "username=admin&password=admin-secret" | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Test streaming chat
curl -X POST http://localhost:8000/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"write a function to sort a list"}' --no-buffer

# Check memory sheet
curl http://localhost:8000/memory -H "Authorization: Bearer $TOKEN"

# Run tests
cd backend && python -m pytest tests/test.py -v

# Check available NIM models
source ../.env && curl -s https://integrate.api.nvidia.com/v1/models \
  -H "Authorization: Bearer $NVIDIA_API_KEY" | python3 -c \
  "import sys,json; [print(m['id']) for m in json.load(sys.stdin).get('data',[])]"
```
