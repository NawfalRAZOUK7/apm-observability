#!/usr/bin/env bash
set -euo pipefail

: "${PRIMARY_HOST:=db}"
: "${PRIMARY_PORT:=5432}"
: "${REPLICA_USER:=replicator}"
: "${REPLICA_PASSWORD:=replicator_pass}"
: "${PGDATA:=/var/lib/postgresql/data}"
: "${PGPASSFILE:=/var/lib/postgresql/.pgpass}"

mkdir -p "$(dirname "$PGPASSFILE")"
echo "${PRIMARY_HOST}:${PRIMARY_PORT}:*:${REPLICA_USER}:${REPLICA_PASSWORD}" > "$PGPASSFILE"
chmod 600 "$PGPASSFILE"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "Initializing replica from primary ${PRIMARY_HOST}:${PRIMARY_PORT}..."
  rm -rf "${PGDATA:?}/"*
  pg_basebackup -h "$PRIMARY_HOST" -p "$PRIMARY_PORT" -U "$REPLICA_USER" -D "$PGDATA" -Fp -Xs -P -R
fi

chmod 700 "$PGDATA"

exec postgres -c hot_standby=on -c port=5432
