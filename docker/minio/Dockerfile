# docker/minio/Dockerfile
# MinIO wrapper image for local dev.
# - Credentials are provided via docker-compose (MINIO_ROOT_USER / MINIO_ROOT_PASSWORD)
# - TLS certs are provided by mounting ./docker/certs -> /root/.minio/certs
#   expecting:
#     /root/.minio/certs/public.crt
#     /root/.minio/certs/private.key
#
# This Dockerfile intentionally does NOT bake secrets or certs into the image.

FROM minio/minio:latest

USER root

# Ensure the cert folders exist (MinIO reads certs from here)
RUN mkdir -p /root/.minio/certs/CAs \
    && chmod -R 700 /root/.minio \
    && chown -R root:root /root/.minio

# The upstream image commonly runs as uid 1000.
# If you ever see permission issues, you can remove this line.
USER 1000

# Command is set in docker-compose (e.g., `minio server /data --console-address ":9001"`).
