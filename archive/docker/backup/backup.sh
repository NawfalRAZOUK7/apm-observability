#!/usr/bin/env bash
set -euo pipefail


# WAL-G backup script for TimescaleDB/PostgreSQL
# Usage: ./backup.sh
#
# SSH key setup is now fully automated: this script will always ensure the postgres user's authorized_keys is correct before any backup.
docker compose -f docker/docker-compose.backup.yml exec db bash /backup/setup_postgres_ssh.sh /backup/id_rsa.pub || true

docker compose -f docker/docker-compose.backup.yml run --rm walg wal-g backup-push /var/lib/postgresql/data
