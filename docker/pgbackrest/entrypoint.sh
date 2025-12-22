#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# docker/pgbackrest/entrypoint.sh
# Option 2 (TLS server / mTLS) — no SSH.
#
# Responsibilities:
# - Ensure required directories exist
# - (Optional) sanity-check config path
# - Exec the provided command
# ============================================================================

# Create dirs in case volume mounts are missing
mkdir -p /etc/pgbackrest /var/lib/pgbackrest /var/log/pgbackrest

# If config is specified, ensure it exists (helps catch bad mounts early)
if [[ -n "${PGBACKREST_CONFIG:-}" ]]; then
  if [[ ! -f "${PGBACKREST_CONFIG}" ]]; then
    echo "ERROR: PGBACKREST_CONFIG points to missing file: ${PGBACKREST_CONFIG}" >&2
    echo "Hint: check your docker-compose mounts for /etc/pgbackrest/pgbackrest.conf" >&2
    exit 1
  fi
fi

# Best-effort: show pgBackRest version for logs
pgbackrest version || true

exec "$@"
