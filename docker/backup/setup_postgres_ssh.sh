#!/bin/bash
# This script sets up SSH key-based auth for the postgres user in the db container.
# Usage: docker compose -f docker/docker-compose.backup.yml exec db bash /backup/setup_postgres_ssh.sh <public_key_file>

set -e

PUBKEY_FILE=${1:-/backup/id_rsa.pub}
SSH_DIR="/var/lib/postgresql/.ssh"
AUTH_KEYS="$SSH_DIR/authorized_keys"

if [ ! -f "$PUBKEY_FILE" ]; then
  echo "Public key file $PUBKEY_FILE not found!"
  exit 1
fi

mkdir -p "$SSH_DIR"
chown postgres:postgres "$SSH_DIR"
chmod 700 "$SSH_DIR"

# Write the public key with no trailing newline or extra characters
tr -d '\r' < "$PUBKEY_FILE" | tr -d '\n' > "$AUTH_KEYS"
echo >> "$AUTH_KEYS" # ensure exactly one newline at end
chown postgres:postgres "$AUTH_KEYS"
chmod 600 "$AUTH_KEYS"
echo "SSH key for postgres user set up successfully."