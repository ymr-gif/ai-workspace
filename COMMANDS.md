# Quick Commands

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

# Run tests (unit tier)
cd backend && python -m pytest tests/test.py -v

# Live E2E tier (paid NIM; stack must be up)
cd backend && RUN_LIVE_NIM=1 VERIFY_BASE_URL=http://localhost:8000 pytest tests/live/ -q -m "live_nim or optional"

# Full-surface feature run (all tiers + every documented feature incl. real mutations + headed UI)
cd backend/tests/latch && bash run_rich_full.sh          # flags: --skip-ui --skip-rotation --skip-live

# Dev SMTP catcher (verify digest/notification email; UI at 127.0.0.1:8025; use SMTP_STARTTLS=false)
docker compose --profile mail up -d mailhog

# Rebuild after backend changes — ALL FOUR backend images (api alone leaves workers stale)
docker compose build api scheduler arq-worker metrics-worker && docker compose up -d --force-recreate api scheduler arq-worker metrics-worker
```
