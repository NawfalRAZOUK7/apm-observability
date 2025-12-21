#!/bin/bash
# cleanup_minio_ca_crt.sh
# Removes the /etc/ssl/certs/minio-ca.crt directory from the pgbackrest container if it exists,
# then restarts the container to allow the file mount to succeed.

set -e

CONTAINER_NAME="pgbackrest"

# Remove the directory if it exists
if docker-compose -f docker/docker-compose.backup.yml exec "$CONTAINER_NAME" test -d /etc/ssl/certs/minio-ca.crt; then
  echo "Removing /etc/ssl/certs/minio-ca.crt directory from $CONTAINER_NAME..."
  docker-compose -f docker/docker-compose.backup.yml exec "$CONTAINER_NAME" rm -rf /etc/ssl/certs/minio-ca.crt
else
  echo "/etc/ssl/certs/minio-ca.crt is not a directory in $CONTAINER_NAME."
fi

# Restart the container to apply the file mount
echo "Restarting $CONTAINER_NAME container..."
docker-compose -f docker/docker-compose.backup.yml restart "$CONTAINER_NAME"

echo "Done. Check the mount with:"
echo "  docker-compose -f docker/docker-compose.backup.yml exec pgbackrest ls -l /etc/ssl/certs/minio-ca.crt"
