#!/bin/sh
# entrypoint.copy-ca.sh - Ensures the CA certificate is copied from the backup mount to the container for pgBackRest SSL operations.
set -e

# Ensure target directory exists
mkdir -p /tmp/ca

# Copy the CA cert from the backup mount if it exists and is a file
if [ -f /backup/public.crt ]; then
    cp /backup/public.crt /tmp/ca/public.crt
    chmod 644 /tmp/ca/public.crt
fi

# Exec the original command
exec "$@"
