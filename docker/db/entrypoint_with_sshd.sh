#!/bin/bash
# entrypoint_with_sshd.sh - Custom entrypoint for the Postgres container with SSHD enabled for backup/restore automation.

# Generate SSH host keys if missing
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
		ssh-keygen -A
fi



# (rsyslogd removed: not required for container operation)

# Start SSH daemon (as root)
/usr/sbin/sshd -D &

# Fix permissions for postgres home and .ssh
chown -R postgres:postgres /var/lib/postgresql && chmod 700 /var/lib/postgresql
if [ -d /var/lib/postgresql/.ssh ]; then
	chown -R postgres:postgres /var/lib/postgresql/.ssh
	chmod 700 /var/lib/postgresql/.ssh
	chmod 600 /var/lib/postgresql/.ssh/authorized_keys || true
fi

# Patch postgresql.conf to use valid locale if present
CONF="/var/lib/postgresql/data/postgresql.conf"
if [ -f "$CONF" ]; then
	sed -i 's/en_US.utf8/C.utf8/g' "$CONF"
fi



# Ensure the default cluster exists with C.UTF-8 locale and postgresql.conf is present
CONF="/var/lib/postgresql/14/main/postgresql.conf"
CLUSTER_DIR="/var/lib/postgresql/14/main"
echo "[DEBUG] Before cluster creation:"
ls -al /var/lib/postgresql/14 || true
ls -al $CLUSTER_DIR || true
id
whoami
echo "[DEBUG] Permissions on parent directory:"
ls -ld /var/lib/postgresql/14

if [ ! -f "$CONF" ]; then
	echo "Cluster not found or config missing, cleaning up and creating with C.UTF-8 locale..."
	pg_dropcluster --stop 14 main || true
	rm -rf $CLUSTER_DIR
	mkdir -p $CLUSTER_DIR
	chown -R postgres:postgres /var/lib/postgresql
	chmod 700 /var/lib/postgresql
	echo "[DEBUG] After cleanup, before creation:"
	ls -al /var/lib/postgresql/14
	ls -al $CLUSTER_DIR
	su - postgres -c "pg_createcluster --locale C.UTF-8 14 main"
	sleep 2
	echo "[DEBUG] After cluster creation:"
	ls -al /var/lib/postgresql/14
	ls -al $CLUSTER_DIR
	ls -l /var/log/postgresql/
fi

# If config is still missing, try again as root with HOME set
if [ ! -f "$CONF" ]; then
	echo "Config still missing after first attempt, retrying as root with HOME set..."
	export HOME=/var/lib/postgresql
	pg_createcluster --locale C.UTF-8 14 main
	sleep 2
	echo "[DEBUG] After root retry:"
	ls -al /var/lib/postgresql/14
	ls -al $CLUSTER_DIR
	ls -l /var/log/postgresql/
fi

# If config is still missing, forcibly re-initialize the cluster directory
if [ ! -f "$CONF" ]; then
	echo "Config still missing after all attempts, forcibly re-initializing with initdb..."
	rm -rf $CLUSTER_DIR
	mkdir -p $CLUSTER_DIR
	chown -R postgres:postgres /var/lib/postgresql
	chmod 700 /var/lib/postgresql
	su - postgres -c "/usr/lib/postgresql/14/bin/initdb -D $CLUSTER_DIR --locale=C.UTF-8 --encoding=UTF8"
	sleep 2
	echo "[DEBUG] After forced initdb:"
	ls -al /var/lib/postgresql/14
	ls -al $CLUSTER_DIR
	ls -l /var/log/postgresql/
fi

# Final check: fail if config is still missing
if [ ! -f "$CONF" ]; then
	echo "ERROR: postgresql.conf is still missing after all attempts. Exiting."
	exit 2
fi


echo "Before starting Postgres:"
ls -l /var/lib/postgresql/14/main
whoami
sleep 2
cat /var/lib/postgresql/14/main/postgresql.conf | head -20

# Patch listen_addresses in postgresql.conf to allow all hosts
CONF="/var/lib/postgresql/14/main/postgresql.conf"
if grep -q "^#listen_addresses" "$CONF"; then
	sed -i "s/^#listen_addresses.*/listen_addresses = '*'" "$CONF"
elif ! grep -q "^listen_addresses" "$CONF"; then
	echo "listen_addresses = '*'" >> "$CONF"
fi

# Start Postgres as postgres user, using the default cluster data directory
exec su - postgres -c "/usr/lib/postgresql/14/bin/postgres -D /var/lib/postgresql/14/main"
