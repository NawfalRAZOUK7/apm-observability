#!/bin/sh
# init.sh - Waits for MinIO to be ready, then uses mc to create the required bucket and list contents.
set -x



# Update CA certificates for mc trust
update-ca-certificates

# Wait for MinIO to be ready (using /minio/health/ready for readiness)
echo "Waiting for MinIO to be ready..."
for i in $(seq 1 30); do
    if curl -k --silent --fail https://minio:9000/minio/health/ready; then
        echo "MinIO is ready."
        break
    fi
    echo "MinIO not ready yet. Waiting ($i/30)..."
    sleep 2
done

# Always use https and the correct host for mc
MC_HOST="https://minio:9000"
echo "Setting mc alias for MinIO at $MC_HOST..."
mc alias set local "$MC_HOST" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
echo "Creating bucket apm-backups if not exists..."
mc mb --ignore-existing local/apm-backups
echo "Listing all buckets:"
mc ls local
echo "Listing apm-backups bucket contents:"
mc ls local/apm-backups
