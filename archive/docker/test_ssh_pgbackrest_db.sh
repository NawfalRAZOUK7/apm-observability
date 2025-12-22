#!/bin/bash

# test_ssh_pgbackrest_db.sh
# Test SSH connection to the db container as postgres user with and without password
#
# SSH key setup is now fully automated: this script will always ensure the postgres user's authorized_keys is correct before any test.
docker compose -f docker/docker-compose.backup.yml exec db bash /backup/setup_postgres_ssh.sh /backup/id_rsa.pub || true

set -e

DB_HOST="db"
DB_USER="postgres"
PRIVATE_KEY="/root/.ssh/id_rsa"
PASSWORD="apm"

# Test passwordless SSH
function test_passwordless() {
    echo "Testing passwordless SSH..."
    ssh -o StrictHostKeyChecking=no -i "$PRIVATE_KEY" "$DB_USER"@"$DB_HOST" hostname && \
        echo "Passwordless SSH: SUCCESS" || echo "Passwordless SSH: FAILED"
}


# Test password-based SSH (requires sshpass)
function test_password() {
    echo "Testing password-based SSH with password: $PASSWORD ..."
    if ! command -v sshpass >/dev/null 2>&1; then
        echo "sshpass not installed. Skipping password-based test."
        return 1
    fi
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$DB_USER"@"$DB_HOST" hostname && \
        echo "Password-based SSH: SUCCESS" || echo "Password-based SSH: FAILED"
}

echo "--- SSH Connection Test Script ---"
test_passwordless
test_password
