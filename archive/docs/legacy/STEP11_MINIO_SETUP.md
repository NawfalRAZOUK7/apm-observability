# Step 11 — MinIO (S3-compatible) setup for local backups

## Purpose

We use MinIO locally to emulate an S3-compatible object store used by pgBackRest (Repo1 = COLD).

## Recommended ports & container command

Typical MinIO Docker runs:

- API on `9000`
- Console on `9001`
  And uses the command format:
- `minio server /data --console-address ":9001"`

## docker-compose snippet (MinIO + bucket auto-create)

Add these services to `docker/docker-compose.backup.yml`:

```yaml
services:
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  # One-shot init container that creates the bucket and (optional) enables versioning.
  minio-init:
    image: minio/mc
    depends_on:
      - minio
    entrypoint: ["/bin/sh", "-lc"]
    command: >
      "
      mc alias set local http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD &&
      mc mb --ignore-existing local/apm-backups &&
      mc ls local &&
      mc ls local/apm-backups
      "
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
volumes:
  minio_data:
```

## Verify MinIO is ready

- Open console: http://localhost:9001
- Login with MINIO_ROOT_USER / MINIO_ROOT_PASSWORD
- Ensure bucket exists: apm-backups

### Why bucket creation matters for pgBackRest

pgBackRest requires the bucket to exist before writing to S3-compatible storage.

### Notes for better demos

- Keep credentials in .env for local dev
- Consider enabling bucket versioning if you want stronger “cold” safety (optional)

### References (MinIO tooling)

- MinIO Docker usage and server command style: see official Docker image docs.
- MinIO client (mc) bucket creation via mc mb command.

**MinIO factual refs used:** MinIO Docker image shows `server /data --console-address ":9001"` usage. :contentReference[oaicite:0]{index=0}  
**MinIO bucket creation command ref (`mc mb`)**: :contentReference[oaicite:1]{index=1}  
