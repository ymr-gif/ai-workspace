# Docker / Infra Reference

## Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn |
| frontend | 3000 | nginx serving React build |
| pgbouncer | — | `edoburu/pgbouncer`; transaction mode; 200 max clients, 20 server conns |
| postgres | — | `pgvector/pgvector:pg16`; internal only |
| redis | — | internal only |
| prometheus | 9090 | scrapes api:8000/metrics every 5s |
| grafana | 3001 | admin/admin, auto-provisioned 24-panel dashboard |
| metrics-worker | — | `python -m observability.metrics_worker` |
| scheduler | — | `python -m services.scheduler_worker`; APScheduler cron runner |

## pgBouncer
- `AUTH_TYPE=plain` required — pg16 uses scram-sha-256; pgBouncer must compute SCRAM from plaintext
- `md5` and `trust` do NOT work with pg16 backend
- api + scheduler `DATABASE_URL` → `pgbouncer:5432` (not `postgres:5432`)
- SQLAlchemy `prepared_statement_cache_size=0` required for transaction mode
- `pool_pre_ping=False` — pgBouncer manages dead connections

## Files
| File | Purpose |
|------|---------|
| `docker-compose.yml` | Main stack |
| `docker-compose.prod.yml` | Production override: nginx TLS, resource limits, redis persistence |
| `backend.Dockerfile` | API + scheduler image |
| `frontend.Dockerfile` | React build + nginx |
| `nginx.conf` | Internal API proxy |
| `nginx.frontend.conf` | Frontend serving |
| `nginx.prod.conf` | TLS termination; replace "example.com" before deploy |
| `backup.sh` | pg_dump + gzip → storage/backups/; prunes after KEEP_DAYS (default 7) |
| `prometheus.yml` | Scrape config |

## Grafana Dashboard (`grafana/provisioning/dashboards/nim-gateway.json`)
24 panels. Two datasources intentionally split:

| Datasource | Panels | Why |
|-----------|--------|-----|
| Prometheus (`uid: prometheus`) | 1-17, 23-24 | Rate queries, timeseries |
| PostgreSQL (`uid: postgres`) | 19-22 | All-time totals — survives container restarts |

Panel layout:
- 1-4: stat row (requests, success rate, cache hit rate, errors)
- 5-6: request rate timeseries, latency p50/p95/p99
- 7-8: model usage rate, model latency p50
- 9-10: cache hits/misses, fallbacks + circuit breaker trips
- 11: row divider "File Knowledge Base"
- 12-15: stat row (uploads, deletes, chunks, tool calls)
- 16: file uploads/deletes/chunks rate/min
- 17: AI tool calls by tool name
- 18: row divider "Token Usage & Cost"
- 19-22: stat row (prompt tokens, completion tokens, total tokens, cost USD) — **PostgreSQL**
- 23: token usage by model (prompt + completion rate/min)
- 24: estimated cost by model ($/hr)

Datasources provisioned via:
- `grafana/provisioning/datasources/prometheus.yml` — uid: prometheus
- `grafana/provisioning/datasources/postgres.yml` — reads POSTGRES_USER/PASSWORD/DB from env
