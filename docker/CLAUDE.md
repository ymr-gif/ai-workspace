# Docker / Infra Reference

## Services & Ports
| Service | Port | Notes |
|---------|------|-------|
| api | 8000 | FastAPI, uvicorn |
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

## Grafana Dashboard
24 panels in `grafana/provisioning/dashboards/nim-gateway.json`

Two datasources intentionally split:
- **Prometheus** (panels 1-17, 23-24) — rate queries, timeseries; resets on restart
- **PostgreSQL** (panels 19-22) — all-time token/cost totals; survives restarts

Panel groups: requests/errors/cache stats · latency p50/p95/p99 · model usage/latency · file uploads/chunks/tool calls · token usage + cost by model

---

## HANDOFF Protocol

On session start — check if `docker/HANDOFF.md` exists:
```bash
ls HANDOFF.md 2>/dev/null && echo "YOUR TURN" || echo "no handoff"
```

If it exists:
1. Read `## dockdir` Tasks section
2. Read all prior `### Recorded` sections — watch for new env vars, ports, volumes, services
3. Execute all tasks (check off as done)
4. Fill `### Recorded` with infra facts (service names, ports, env var defaults)
5. **Update `docker/CLAUDE.md`** — add any new services, ports, volumes, or env vars introduced by the feature
6. Append a History row
7. Move file back to root (set status: done first):
   ```bash
   mv HANDOFF.md ../HANDOFF.md
   ```
