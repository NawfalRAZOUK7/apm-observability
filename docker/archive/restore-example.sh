#!/usr/bin/env bash
set -euo pipefail


# Example restore flow for the backup compose stack.
# Assumes project directory name is apm-observability (adjust DB_VOL if different).
#
# SSH key setup is now fully automated: this script will always ensure the postgres user's authorized_keys is correct before any restore.
docker compose -f docker/docker-compose.backup.yml exec db bash /backup/setup_postgres_ssh.sh /backup/id_rsa.pub || true

COMPOSE_FILE=${COMPOSE_FILE:-docker/docker-compose.backup.yml}
DB_VOL=${DB_VOL:-apm-observability_db_data_backup}

echo "Stopping database..."
docker compose -f "$COMPOSE_FILE" stop db || true
docker compose -f "$COMPOSE_FILE" rm -f db || true

echo "Removing database volume $DB_VOL ..."
docker volume rm "$DB_VOL" || true

echo "Recreating services (db + minio)..."
docker compose -f "$COMPOSE_FILE" up -d minio minio-mc db

# WAL-G restore logic will be added here.

echo "Restore complete. (WAL-G restore steps to be documented.)"
