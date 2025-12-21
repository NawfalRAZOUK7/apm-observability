#!/bin/bash
# Usage: ./switch_pgbackrest_mode.sh [tcp|ssh]
# Switches pgBackRest config by copying the right file.
# Edits docker/backup/pgbackrest.conf in-place.

MODE="$1"
DIR="$(dirname "$0")"
if [[ "$MODE" == "tcp" ]]; then
    cp "$DIR/pgbackrest.tcp.conf" "$DIR/pgbackrest.conf"
    echo "Switched to TCP mode."
elif [[ "$MODE" == "ssh" ]]; then
    cp "$DIR/pgbackrest.ssh.conf" "$DIR/pgbackrest.conf"
    echo "Switched to SSH mode."
else
    echo "Usage: $0 [tcp|ssh]"
    exit 1
fi
