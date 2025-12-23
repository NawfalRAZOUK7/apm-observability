#!/usr/bin/env bash
set -euo pipefail

: "${PGBACKREST_CONFIG:=/etc/pgbackrest/pgbackrest.conf}"
: "${PGBACKREST_REPO1_CIPHER_PASS:=}"
: "${PGBACKREST_REPO2_CIPHER_PASS:=}"

LOG_FILE="/var/log/pgbackrest/cron.log"
mkdir -p /var/log/pgbackrest
touch "$LOG_FILE"

cat > /etc/cron.d/pgbackrest <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
CRON_TZ=UTC
PGBACKREST_CONFIG=${PGBACKREST_CONFIG}
PGBACKREST_REPO1_CIPHER_PASS=${PGBACKREST_REPO1_CIPHER_PASS}
PGBACKREST_REPO2_CIPHER_PASS=${PGBACKREST_REPO2_CIPHER_PASS}

# Hourly incremental (repo1)
0 * * * * root pgbackrest --stanza=apm --type=incr backup >> ${LOG_FILE} 2>&1
# Daily differential (repo1)
0 1 * * * root pgbackrest --stanza=apm --type=diff backup >> ${LOG_FILE} 2>&1
# Weekly full (repo1) - Sunday 01:05
5 1 * * 0 root pgbackrest --stanza=apm --type=full backup >> ${LOG_FILE} 2>&1
# Monthly full (repo2) - First Sunday 02:00
0 2 1-7 * 0 root pgbackrest --stanza=apm --repo=2 --type=full backup >> ${LOG_FILE} 2>&1
EOF

chmod 0644 /etc/cron.d/pgbackrest

exec cron -f
