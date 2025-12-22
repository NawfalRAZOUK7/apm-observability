#!/usr/bin/env bash
set -euo pipefail


# WAL-G restore script for TimescaleDB/PostgreSQL
# Usage: ./restore.sh
#
# SSH key setup is now fully automated: this script will always ensure the postgres user's authorized_keys is correct before any restore.
docker compose -f docker/docker-compose.backup.yml exec db bash /backup/setup_postgres_ssh.sh /backup/id_rsa.pub || true

COMPOSE_FILE=docker/docker-compose.backup.yml
DB_VOL=apm-observability_db_data_backup

# Stop and remove the database container and volume

echo "Stopping database..."
docker compose -f "$COMPOSE_FILE" stop db || true
docker compose -f "$COMPOSE_FILE" rm -f db || true

echo "Removing database volume $DB_VOL ..."
docker volume rm "$DB_VOL" || true

echo "Recreating services (db + minio + walg)..."
docker compose -f "$COMPOSE_FILE" up -d minio minio-mc db walg

# Give the database a moment to start before restore.
sleep 5

echo "Restoring latest backup into fresh volume..."
docker compose -f "$COMPOSE_FILE" run --rm walg wal-g backup-fetch /var/lib/postgresql/data LATEST

echo "Restarting database..."
docker compose -f "$COMPOSE_FILE" up -d db

echo "Restore complete. Verify with: docker compose -f $COMPOSE_FILE exec db psql -U ${POSTGRES_USER:-apm} -d ${POSTGRES_DB:-apm} -c 'select count(*) from api_request limit 1;'"
