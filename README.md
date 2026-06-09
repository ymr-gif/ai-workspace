# NIM AI Gateway

A self-hosted AI chat backend routing requests to [NVIDIA NIM](https://build.nvidia.com/) models. FastAPI + React/Vite, fully containerized via Docker Compose.

---

## Features

- **Multi-model routing** — keyword classifier picks llama / coder / reasoning; per-request and per-conversation model lock supported
- **SSE streaming** — real-time token streaming to the frontend
- **Hybrid RAG** — pgvector + BM25 fusion retrieval; adaptive policy per query type
- **Graph memory** — Neo4j entity extraction; per-user knowledge graph persists across sessions
- **Multi-tier memory** — compressed history, project summary, salience-ranked facts, memory compaction
- **AI agent tool loop** — file read/write/patch, graph queries, memory writes; loop-guarded with circuit abort
- **File knowledge base** — upload PDF, DOCX, XLSX, plain text; SHA-256 dedup; chunk + embed pipeline
- **Auth** — JWT + API key fallback (SHA-256 hashed); bcrypt passwords; invite-gated registration; role-based access
- **Rate limiting** — sliding-window per user (15 req/60s) + per model; Redis-backed
- **Circuit breaker** — 5 failures → open; 90s cooldown; pre-tripped on startup if model is unreachable
- **Observability** — Prometheus + Grafana; activity trace per message; structured logs
- **Admin panel** — user management, per-user cost limits, live env management, audit log

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic |
| Frontend | React, Vite, TypeScript |
| Database | PostgreSQL + pgvector |
| Cache | Redis |
| Graph | Neo4j |
| Monitoring | Prometheus, Grafana |
| Runtime | Docker Compose |
| AI | NVIDIA NIM API |

---

## Models

| Role | Model |
|---|---|
| General | `meta/llama-3.1-8b-instruct` |
| Coder | `deepseek-ai/deepseek-v4-flash` |
| Reasoning | `meta/llama-3.3-70b-instruct` |
| Embedding | `nvidia/nv-embedqa-e5-v5` (1024d) |

---

## Quickstart

### Prerequisites
- Docker + Docker Compose
- NVIDIA NIM API key — [build.nvidia.com](https://build.nvidia.com/)

### 1. Clone
```bash
git clone https://github.com/ymr-gif/ai-workspace.git
cd ai-workspace
```

### 2. Configure
```bash
cp .env.example .env
```

Minimum required values:
```env
NVIDIA_API_KEY=your_key_here
JWT_SECRET_KEY=your_random_secret
```

### 3. Start
```bash
cd docker && docker compose up -d
```

Frontend: `http://localhost:5173`  
API docs: `http://localhost:8000/docs`  
Grafana: `http://localhost:3000`

---

## API

All endpoints require `Authorization: Bearer <token>` unless noted.

### Auth
```bash
# Login
POST /auth/token
form: username, password

# Register (invite required by default)
POST /auth/register
json: { username, password, invite_token }
```

### Chat
```bash
# Streaming (SSE)
POST /chat/stream
json: { message, conversation_id?, model_override?, file_ids? }

# Non-streaming
POST /chat
```

### Conversations
```bash
GET  /conversations          # list with optional ?q= search
GET  /conversations/{id}/messages
DELETE /conversations/{id}
GET  /conversations/{id}/export
```

### Files
```bash
POST /files/upload           # multipart
GET  /files
DELETE /files/{id}
```

### Memory & Graph
```bash
GET  /memory
GET  /graph/stats
GET  /graph/sample
```

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `NVIDIA_API_KEY` | NIM API key |
| `JWT_SECRET_KEY` | Secret for JWT signing |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `NEO4J_URI` | Neo4j bolt URI |
| `REQUIRE_INVITE` | `true` to gate registration behind invites |
| `MODEL_LLAMA` / `MODEL_CODER` / `MODEL_REASONING` | Override default model IDs |
| `REQUEST_TIMEOUT` | NIM request timeout in seconds (default 30) |

---

## Project Structure

```
ai-api/
├── backend/          — FastAPI app (auth, chat, files, memory, agent, admin)
├── frontend/         — React/Vite UI
└── docker/           — Compose files, Dockerfiles, Grafana dashboards
```

---

## License

MIT
