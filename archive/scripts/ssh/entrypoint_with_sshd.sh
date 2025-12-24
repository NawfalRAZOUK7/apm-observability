#!/bin/bash

# Generate SSH host keys
ssh-keygen -A

# Create postgres SSH directory
mkdir -p /var/lib/postgresql/.ssh
chown postgres:postgres /var/lib/postgresql/.ssh
chmod 700 /var/lib/postgresql/.ssh

# Generate SSH keys for postgres user
if [ ! -f /var/lib/postgresql/.ssh/id_rsa ]; then
    su - postgres -c "ssh-keygen -t rsa -b 2048 -f /var/lib/postgresql/.ssh/id_rsa -N ''"
    su - postgres -c "cat /var/lib/postgresql/.ssh/id_rsa.pub >> /var/lib/postgresql/.ssh/authorized_keys"
    chmod 600 /var/lib/postgresql/.ssh/authorized_keys
    chown postgres:postgres /var/lib/postgresql/.ssh/authorized_keys
fi

# Set permissions
chown -R postgres:postgres /var/lib/postgresql

# Start SSH daemon
/usr/sbin/sshd -D &

# Initialize PostgreSQL if needed
if [ ! -f "/var/lib/postgresql/data/PG_VERSION" ]; then
    su - postgres -c "initdb -D /var/lib/postgresql/data --locale=C.UTF-8 --encoding=UTF-8"
fi

# Configure postgresql.conf for backups
CONF="/var/lib/postgresql/data/postgresql.conf"
if [ -f "$CONF" ]; then
    sed -i 's/#*wal_level.*/wal_level = replica/' "$CONF"
    sed -i 's/#*archive_mode.*/archive_mode = on/' "$CONF"
    sed -i "s|#*archive_command.*|archive_command = 'pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm archive-push %p'|" "$CONF"
    sed -i 's/#*listen_addresses.*/listen_addresses = '\''*'\''/' "$CONF"
fi

# Start PostgreSQL
exec su - postgres -c "postgres -D /var/lib/postgresql/data"
