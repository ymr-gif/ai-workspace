#!/usr/bin/env bash
# Postgres backup — dumps and gzips the DB, prunes old backups.
# Run from anywhere; paths are relative to this script's directory.
#
# Env vars (all optional, fall back to docker-compose.yml defaults):
#   POSTGRES_USER    default: scylla
#   POSTGRES_DB      default: nimrouter
#   BACKUP_DIR       default: ../backend/storage/backups
#   KEEP_DAYS        default: 7

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POSTGRES_USER="${POSTGRES_USER:-scylla}"
POSTGRES_DB="${POSTGRES_DB:-nimrouter}"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/../backend/storage/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${POSTGRES_DB}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] dumping ${POSTGRES_DB} → ${BACKUP_FILE}"

docker compose -f "$SCRIPT_DIR/docker-compose.yml" exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"

SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo "[backup] done: ${SIZE}"

# Prune backups older than KEEP_DAYS
PRUNED=$(find "$BACKUP_DIR" -name "${POSTGRES_DB}_*.sql.gz" -mtime "+${KEEP_DAYS}" -print -delete | wc -l)
echo "[backup] pruned ${PRUNED} backup(s) older than ${KEEP_DAYS} days"

# To restore:
#   gunzip -c <file>.sql.gz | docker compose exec -T postgres psql -U $POSTGRES_USER $POSTGRES_DB
