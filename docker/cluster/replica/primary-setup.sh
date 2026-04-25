#!/usr/bin/env bash
set -euo pipefail

: "${REPLICA_USER:=replicator}"
: "${REPLICA_PASSWORD:=replicator_pass}"
: "${REPLICA_CIDR:=0.0.0.0/0}"
: "${PGDATA:=/var/lib/postgresql/data}"

psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${REPLICA_USER}') THEN
    CREATE ROLE ${REPLICA_USER} WITH REPLICATION LOGIN PASSWORD '${REPLICA_PASSWORD}';
  ELSE
    ALTER ROLE ${REPLICA_USER} WITH REPLICATION LOGIN PASSWORD '${REPLICA_PASSWORD}';
  END IF;
END \$\$;
SQL

line="host replication ${REPLICA_USER} ${REPLICA_CIDR} md5"
if ! grep -Fq "$line" "$PGDATA/pg_hba.conf"; then
  echo "$line" >> "$PGDATA/pg_hba.conf"
fi

psql -v ON_ERROR_STOP=1 -c "SELECT pg_reload_conf();"
