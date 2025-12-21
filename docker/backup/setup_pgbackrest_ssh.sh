#!/bin/bash
# setup_pgbackrest_ssh.sh
# Generate SSH key if not present, distribute public key, and install sshpass for testing.
set -e

# Generate SSH key if not present
if [ ! -f /backup/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -N "" -f /backup/id_rsa
fi

# Copy public key to db container's authorized_keys
PUBKEY=$(cat /backup/id_rsa.pub)
docker compose -f /workspace/docker/docker-compose.backup.yml exec db bash -c "mkdir -p /var/lib/postgresql/.ssh && echo '$PUBKEY' >> /var/lib/postgresql/.ssh/authorized_keys && chown -R postgres:postgres /var/lib/postgresql/.ssh && chmod 700 /var/lib/postgresql/.ssh && chmod 600 /var/lib/postgresql/.ssh/authorized_keys"

# Install sshpass in pgbackrest container if not present
if ! docker compose -f /workspace/docker/docker-compose.backup.yml exec pgbackrest which sshpass >/dev/null 2>&1; then
    docker compose -f /workspace/docker/docker-compose.backup.yml exec pgbackrest apt-get update
    docker compose -f /workspace/docker/docker-compose.backup.yml exec pgbackrest apt-get install -y sshpass
fi

echo "SSH key setup and sshpass installation complete."
