# Docker / Infra Reference

## Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn; runs `alembic upgrade head` before start |
| frontend | 3000 | nginx serving React build |
| pgbouncer | — | transaction mode; 200 max clients, 20 server conns |
| postgres | — | `pgvector/pgvector:pg16`; internal only |
| redis | — | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s |
| grafana | 3001 | admin/admin; 24-panel auto-provisioned dashboard |
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
| `nginx.frontend.conf` | Frontend serving |
| `nginx.prod.conf` | TLS termination; replace "example.com" before deploy |
| `backup.sh` | pg_dump + gzip → storage/backups/; prunes after KEEP_DAYS (default 7) |
| `prometheus.yml` | Scrape config |
| `grafana/provisioning/datasources/prometheus.yml` | uid: prometheus |
| `grafana/provisioning/datasources/postgres.yml` | reads POSTGRES_USER/PASSWORD/DB from env |

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
- Postgres: `postgresdata` volume
- Neo4j: `neo4jdata` volume
- Redis: ephemeral by default; `docker-compose.prod.yml` adds `redisdata` with append-only file

## Grafana
24 panels, 2 datasources: Prometheus (rates, resets on restart) + PostgreSQL (all-time totals, survives restarts).

---

## HANDOFF Protocol — Quick Reference

- **Role:** docker worker. Do not plan or delegate.
- **Scope:** `docker/` files only. Cross-dir → `HANDOFF.md` section + pass.
- **Root escalation:** do not edit `.env` `.env.example` `.gitignore` `.dockerignore` root `CLAUDE.md` `README.md` `ROADMAP.md`. Set `status: needs-root`.
- **Session start:** `ls HANDOFF.md` → if exists, read `## dockdir`, execute tasks, fill `### Recorded` (ports, volumes, env var defaults), update this file, append History, `mv HANDOFF.md ../HANDOFF.md`.
- **Append only** — never rewrite this file.

> Full protocol: `../HANDOFF_PROTOCOL.md`
