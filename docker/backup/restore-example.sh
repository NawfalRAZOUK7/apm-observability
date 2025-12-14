#!/usr/bin/env bash
set -euo pipefail

# Example restore flow for the backup compose stack.
# Assumes project directory name is apm-observability (adjust DB_VOL if different).

COMPOSE_FILE=${COMPOSE_FILE:-docker/docker-compose.backup.yml}
DB_VOL=${DB_VOL:-apm-observability_db_data_backup}

echo "Stopping database..."
docker compose -f "$COMPOSE_FILE" stop db || true
docker compose -f "$COMPOSE_FILE" rm -f db || true

echo "Removing database volume $DB_VOL ..."
docker volume rm "$DB_VOL" || true

echo "Recreating services (db + minio + backrest)..."
docker compose -f "$COMPOSE_FILE" up -d minio minio-mc db pgbackrest

# Give the database a moment to start before restore.
sleep 5

echo "Restoring latest backup into fresh volume..."
docker compose -f "$COMPOSE_FILE" run --rm pgbackrest \
  pgbackrest --stanza=apm --delta --type=default restore

echo "Restarting database..."
docker compose -f "$COMPOSE_FILE" up -d db

echo "Restore complete. Verify with: docker compose -f $COMPOSE_FILE exec db psql -U ${POSTGRES_USER:-apm} -d ${POSTGRES_DB:-apm} -c 'select count(*) from api_request limit 1;'"
