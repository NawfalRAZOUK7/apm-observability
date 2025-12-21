#!/bin/bash
# Usage: ./pgbackrest_mode.sh [tcp|ssh] [command ...]
# Switches config, then runs the given pgBackRest or psql command in the right mode.
# Example: ./pgbackrest_mode.sh tcp stanza-create
#          ./pgbackrest_mode.sh ssh check
#          ./pgbackrest_mode.sh backup
#          ./pgbackrest_mode.sh restore
#          ./pgbackrest_mode.sh test-psql
#          ./pgbackrest_mode.sh tcp psql -h db -U apm -d postgres -c "select 1;"

MODE="$1"
SCRIPT_DIR="$(dirname "$0")"

# If first arg is not tcp or ssh, default to tcp and treat as command
if [[ "$MODE" != "tcp" && "$MODE" != "ssh" ]]; then
  CMD="$MODE"
  MODE="tcp"
  shift 0
else
  shift
  CMD="$1"
  shift
fi


# Always ensure SSH key setup if switching to SSH mode
"$SCRIPT_DIR/switch_pgbackrest_mode.sh" "$MODE"
if [[ "$MODE" == "ssh" ]]; then
  # Run SSH key setup in db container (idempotent)
  echo "Ensuring SSH key setup for postgres user in db container..."
  docker compose -f "$SCRIPT_DIR/../docker-compose.backup.yml" exec db bash /backup/setup_postgres_ssh.sh /backup/id_rsa.pub || true
fi


# Helper: run in container, with optional logging
run_pgbackrest() {
  if [ "$LOG_OUTPUT" = "1" ]; then
    TS=$(date +%Y%m%d_%H%M%S)
    LOGFILE="$SCRIPT_DIR/pgbackrest_${MODE}_${CMD}_$TS.log"
    docker compose -f "$SCRIPT_DIR/../docker-compose.backup.yml" exec pgbackrest "$@" | tee "$LOGFILE"
    echo "Output logged to $LOGFILE"
  else
    docker compose -f "$SCRIPT_DIR/../docker-compose.backup.yml" exec pgbackrest "$@"
  fi
}

case "$CMD" in
  "mode")
    # Show current mode by inspecting pgbackrest.conf
    if grep -q 'pg1-host-type=ssh' "$SCRIPT_DIR/pgbackrest.conf"; then
      echo "Current mode: SSH"
    else
      echo "Current mode: TCP"
    fi
    ;;
  "diff")
    # Show diff between TCP and SSH configs
    diff -u "$SCRIPT_DIR/pgbackrest.tcp.conf" "$SCRIPT_DIR/pgbackrest.ssh.conf" || true
    ;;
  "validate")
    # Validate config syntax (basic)
    if grep -q '\[apm\]' "$SCRIPT_DIR/pgbackrest.conf" && grep -q 'repo1-type=' "$SCRIPT_DIR/pgbackrest.conf"; then
      echo "pgbackrest.conf appears valid."
    else
      echo "pgbackrest.conf may be missing required fields!"
    fi
    ;;
  "log")
    # Enable logging for this run
    LOG_OUTPUT=1
    shift; CMD="$1"; shift; $0 "$MODE" "$CMD" "$@"
    ;;
  "stanza-create")
    run_pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm stanza-create
    ;;
  "stanza-delete")
    run_pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm stanza-delete
    ;;
  "check")
    run_pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm check
    ;;
  "backup")
    run_pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm backup
    ;;
  "restore")
    run_pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm restore
    ;;
  "expire")
    run_pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm expire
    ;;
  "info")
    run_pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm info
    ;;
  "list")
    run_pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm info | grep backup: || true
    ;;
  "test-psql")
    run_pgbackrest sh -lc 'PGPASSFILE=/etc/pgbackrest/.pgpass psql -h db -U apm -d postgres -c "select 1;"'
    ;;
  "help"|"--help"|"-h")
    echo "Usage: $0 [tcp|ssh] <command>"
    echo "Shortcuts:"
    echo "  stanza-create   - Create stanza"
    echo "  stanza-delete   - Delete stanza"
    echo "  check           - Check stanza"
    echo "  backup          - Run backup"
    echo "  restore         - Restore backup"
    echo "  expire          - Expire old backups"
    echo "  info            - Show backup info"
    echo "  list            - List backups (summary)"
    echo "  test-psql       - Test DB connection"
    echo "  mode            - Show current mode (TCP/SSH)"
    echo "  diff            - Show config diff (tcp vs ssh)"
    echo "  validate        - Basic config validation"
    echo "  log <cmd>       - Run any shortcut and log output to a timestamped file"
    echo "  help            - Show this help"
    echo "Any other command is passed to the pgbackrest container."
    ;;
  "")
    echo "No command given. Use 'help' for options."
    ;;
  *)
    # Pass through any other command
    run_pgbackrest "$CMD" "$@"
    ;;
esac
