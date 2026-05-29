# Docker / Infra Reference

## Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn; runs `alembic upgrade head` before start |
| frontend | 3000 | nginx serving React build |
| pgbouncer | — | transaction mode; 200 max clients, 20 server conns |
| postgres | — | `pgvector/pgvector:pg16`; internal only |
| redis | — | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s; `prometheusdata` volume persists TSDB across restarts |
| grafana | 3001 | admin/admin; 24-panel auto-provisioned dashboard; unified alerting enabled; 2 alert rules provisioned |
| metrics-worker | — | `python -m observability.metrics_worker` |
| arq-worker | — | `python -m arq services.arq_worker.WorkerSettings`; max_jobs=10 |
| scheduler | — | `python -m services.scheduler_worker` |
| neo4j | 7474 (browser), 7687 (bolt) | `neo4j:5`; auth `neo4j/${NEO4J_PASSWORD:-changeme}`; volume `neo4jdata` |

---

## Migration Safety

- `backend.Dockerfile` CMD runs `alembic upgrade head` before uvicorn — migrations apply automatically on every container start
- **Never use `alembic stamp <rev>`** without also running the actual DDL. Stamping marks a migration as applied in the `alembic_version` table without executing it — columns will be missing, causing 500 errors on startup
- If a stamp was used by mistake: manually apply the missing DDL via `docker exec docker-postgres-1 psql -U <user> -d <db>`, then let alembic continue from that point
- To check actual DB columns vs ORM: `docker exec docker-postgres-1 psql -U scylla -d nimrouter -c "\d <table>"`
- To check alembic state: `docker exec docker-api-1 bash -c "cd /app/backend && alembic current"`

---

## pgBouncer (critical invariants)
- `AUTH_TYPE=plain` required — pg16 uses scram-sha-256; md5/trust do NOT work
- `DATABASE_URL` for api + scheduler → `pgbouncer:5432` (not `postgres:5432`)
- SQLAlchemy `prepared_statement_cache_size=0` required for transaction mode
- `pool_pre_ping=False` — pgBouncer manages dead connections

---

## Files
| File | Purpose |
|------|---------|
| `docker-compose.yml` | Main stack |
| `docker-compose.prod.yml` | nginx TLS, resource limits, redis persistence |
| `backend.Dockerfile` | API + scheduler image |
| `frontend.Dockerfile` | React build + nginx |
| `nginx.conf` | Internal API proxy |
| `nginx.frontend.conf` | Frontend serving; `resolver 127.0.0.11 valid=10s` + `set $upstream api` forces Docker DNS re-resolution so frontend doesn't cache stale api container IPs after rebuild; `rewrite ^/api/(.*) /$1 break` strips the prefix (variable proxy_pass does NOT auto-strip location prefix) |
| `nginx.prod.conf` | TLS termination; replace "example.com" before deploy |
| `backup.sh` | pg_dump + gzip → storage/backups/; prunes after KEEP_DAYS (default 7) |
| `prometheus.yml` | Scrape config |
| `grafana/provisioning/datasources/prometheus.yml` | uid: prometheus |
| `grafana/provisioning/datasources/postgres.yml` | reads POSTGRES_USER/PASSWORD/DB from env |
| `grafana/provisioning/alerting/nim-alerts.yml` | 2 unified alert rules: circuit breaker trip (rate>0 for 1m), success rate <99% for 1m |

---

## Commands
```bash
docker compose up -d                                         # start stack
docker compose down -v --remove-orphans                      # full reset (wipes volumes)
docker compose build --no-cache api && docker compose up -d api   # rebuild api
docker compose logs -f api                                   # tail api logs
./backup.sh                                                  # pg_dump → storage/backups/
```

## Persistence
- Postgres: `pgdata` volume
- Neo4j: `neo4jdata` volume
- Prometheus: `prometheusdata` volume (`/prometheus`) — TSDB survives container restarts
- Redis: ephemeral by default; `docker-compose.prod.yml` adds `redisdata` with append-only file

## api Service — Prometheus Multiprocess Mode
- `PROMETHEUS_MULTIPROC_DIR=/tmp/prom_multiproc` env set; `tmpfs: /tmp/prom_multiproc` mounted
- All uvicorn workers share one metric dir; survives worker restarts within the container (not container restarts)
- `/metrics` endpoint uses `MultiProcessCollector` when env var is present

## Grafana
24 panels, 2 datasources: Prometheus (rates) + PostgreSQL (all-time totals).
- `GF_UNIFIED_ALERTING_ENABLED=true` — required for alerting provisioning
- "Total Errors" panel queries `api_requests_total{status=~"error|partial"}` (not `api_errors_total`)
- "Request Rate" panel shows `partial` series in orange (mid-stream failures)

---

## HANDOFF Protocol — Quick Reference

- **Role:** docker worker. Do not plan or delegate.
- **Scope:** `docker/` files only. Cross-dir → `HANDOFF.md` section + pass.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## dockdir`, execute tasks, fill `### Recorded` (ports, volumes, env var defaults), update this file, append History, `mv HANDOFF.md ../HANDOFF.md`.
- **Append only** — never rewrite this file.

> Full protocol: `../HANDOFF_PROTOCOL.md`
