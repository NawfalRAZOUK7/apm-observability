#!/bin/sh
# Collect logs from minio-init container and save to a timestamped file
LOG_DIR="$(dirname "$0")/../logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/minio-init-$(date +%Y%m%d-%H%M%S).log"
docker logs docker-minio-init-1 > "$LOG_FILE"
echo "Logs saved to $LOG_FILE"