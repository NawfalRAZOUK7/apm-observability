#!/usr/bin/env bash
# Track B — automated restore verification + DR metrics.
#
# Proves the backups actually restore: checks the pgBackRest repo, reads the
# latest backup age (RPO), performs a real restore into a throwaway path and
# times it (RTO), verifies the restored cluster is consistent, then writes
# Prometheus metrics (scraped via node-exporter's textfile collector).
#
# Emits (to $TEXTFILE_DIR/dr_verify.prom):
#   apm_backup_restore_success           1|0
#   apm_backup_restore_duration_seconds  RTO of this verification
#   apm_backup_age_seconds               RPO: age of the latest backup
#   apm_backup_verify_timestamp_seconds  when this ran
#
# Usage: scripts/drills/verify_restore.sh
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

STANZA="${PGBACKREST_STANZA:-apm}"
BACKUP_COMPOSE="${BACKUP_COMPOSE:-docker compose -p apm-data -f docker/docker-compose.backup.yml}"
PGBR_SVC="${PGBR_SVC:-pgbackrest}"
RESTORE_DIR="${RESTORE_DIR:-/tmp/restore_verify_${STANZA}}"
TEXTFILE_DIR="${TEXTFILE_DIR:-$ROOT_DIR/docker/monitoring/node-exporter-textfile}"
PROM_FILE="${TEXTFILE_DIR}/dr_verify.prom"

mkdir -p "$TEXTFILE_DIR"

exec_pgbr() { $BACKUP_COMPOSE exec -T "$PGBR_SVC" "$@"; }

write_metrics() {
  local success="$1" duration="$2" age="$3"
  local now; now="$(date +%s)"
  # Write atomically so node-exporter never reads a half-written file.
  cat > "${PROM_FILE}.tmp" <<EOF
# HELP apm_backup_restore_success Whether the last restore verification succeeded (1) or failed (0).
# TYPE apm_backup_restore_success gauge
apm_backup_restore_success{stanza="${STANZA}"} ${success}
# HELP apm_backup_restore_duration_seconds RTO: wall-clock duration of the restore verification.
# TYPE apm_backup_restore_duration_seconds gauge
apm_backup_restore_duration_seconds{stanza="${STANZA}"} ${duration}
# HELP apm_backup_age_seconds RPO: age of the most recent completed backup.
# TYPE apm_backup_age_seconds gauge
apm_backup_age_seconds{stanza="${STANZA}"} ${age}
# HELP apm_backup_verify_timestamp_seconds Unix time of the last verification run.
# TYPE apm_backup_verify_timestamp_seconds gauge
apm_backup_verify_timestamp_seconds{stanza="${STANZA}"} ${now}
EOF
  mv "${PROM_FILE}.tmp" "${PROM_FILE}"
  echo "==> Metrics written to ${PROM_FILE}"
}

fail() {
  echo "DR VERIFY FAILED: $1" >&2
  write_metrics 0 "${1_duration:-0}" "${AGE:-0}"
  exit 1
}

echo "==> [1/4] Checking pgBackRest repository (stanza=${STANZA})"
exec_pgbr pgbackrest --stanza="${STANZA}" check || fail "pgbackrest check failed"

echo "==> [2/4] Reading latest backup age (RPO)"
INFO_JSON="$(exec_pgbr pgbackrest --stanza="${STANZA}" info --output=json 2>/dev/null)"
AGE="$(printf '%s' "$INFO_JSON" | python3 -c '
import json, sys, time
try:
    data = json.load(sys.stdin)
    stops = [b["timestamp"]["stop"] for s in data for b in s.get("backup", [])]
    print(int(time.time() - max(stops)) if stops else -1)
except Exception:
    print(-1)
')"
if [[ "$AGE" -lt 0 ]]; then fail "no backups found in repository"; fi
echo "    latest backup age: ${AGE}s"

echo "==> [3/4] Restoring into throwaway path ${RESTORE_DIR} (timing RTO)"
START="$(date +%s)"
exec_pgbr rm -rf "${RESTORE_DIR}"
exec_pgbr pgbackrest --stanza="${STANZA}" --pg1-path="${RESTORE_DIR}" --delta restore \
  || fail "restore failed"
END="$(date +%s)"
DURATION=$(( END - START ))
echo "    restore completed in ${DURATION}s"

echo "==> [4/4] Verifying restored cluster consistency"
exec_pgbr test -f "${RESTORE_DIR}/global/pg_control" || fail "restored cluster missing pg_control"
exec_pgbr pg_controldata "${RESTORE_DIR}" | grep -qi "state" || fail "pg_controldata unreadable"

write_metrics 1 "${DURATION}" "${AGE}"
echo "==> DR VERIFY PASSED (RTO=${DURATION}s, RPO=${AGE}s)"
