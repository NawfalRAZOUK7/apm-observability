You hit **two separate issues**:

1. `ghcr.io/pgbackrest/pgbackrest:latest` **doesn’t exist** (no such image/tag), so Compose can’t pull it. (On Docker Hub, the `pgbackrest` org mainly publishes `pgbackrest/test` and `pgbackrest/doc`, not a runtime “pgbackrest” image.)
2. The warnings about `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` happen because Compose is trying to substitute `$MINIO_ROOT_USER` **from your Mac environment** while parsing the YAML (not from the container env).

Below is the clean fix.

---

## Fix 1 — Remove the invalid pgBackRest image and build your own “pgbackrest runner” container

### A) Create `docker/pgbackrest/Dockerfile`

(Compose file is in `docker/`, so paths below are relative to that folder.)

```dockerfile
FROM debian:bookworm-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends pgbackrest cron ca-certificates postgresql-client \
  && rm -rf /var/lib/apt/lists/*

# pgBackRest standard dirs
RUN mkdir -p /etc/pgbackrest /var/log/pgbackrest /var/lib/pgbackrest /var/lib/pgbackrest-hot

# Cron schedule
COPY pgbackrest-cron /etc/cron.d/pgbackrest
RUN chmod 0644 /etc/cron.d/pgbackrest && crontab /etc/cron.d/pgbackrest

CMD ["cron", "-f"]
```

### B) Create `docker/pgbackrest/pgbackrest-cron`

This example schedule matches your Step 11 plan (incr hourly, diff 6h, full daily, expire daily):

```cron
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Hourly incremental to HOT repo2
0 * * * * pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm --repo=2 --type=incr backup >>/proc/1/fd/1 2>>/proc/1/fd/2

# Every 6 hours differential to HOT repo2
15 */6 * * * pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm --repo=2 --type=diff backup >>/proc/1/fd/1 2>>/proc/1/fd/2

# Daily full to COLD repo1 (MinIO/S3)
0 2 * * * pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm --repo=1 --type=full backup >>/proc/1/fd/1 2>>/proc/1/fd/2

# Daily full to HOT repo2
5 2 * * * pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm --repo=2 --type=full backup >>/proc/1/fd/1 2>>/proc/1/fd/2

# Expire daily (retention cleanup)
0 3 * * * pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm --repo=1 expire >>/proc/1/fd/1 2>>/proc/1/fd/2
5 3 * * * pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm --repo=2 expire >>/proc/1/fd/1 2>>/proc/1/fd/2
```

### C) Update the `pgbackrest` service in `docker-compose.backup.yml`

Replace your current pgbackrest service with:

```yaml
  pgbackrest:
    build:
      context: .
      dockerfile: pgbackrest/Dockerfile
    container_name: pgbackrest
    depends_on:
      - db
      - minio
    volumes:
      - ./backup/pgbackrest.conf:/etc/pgbackrest/pgbackrest.conf:ro
      - pgdata:/var/lib/postgresql/data:ro
      - pgbackrest-hot:/var/lib/pgbackrest-hot
    networks:
      - backup-net
```

✅ This avoids relying on a non-existent image and gives you a working cron-based runner.

---

## Fix 2 — Remove the `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` warnings

### Why you get those warnings

In your `minio-init` command you wrote `$MINIO_ROOT_USER` and `$MINIO_ROOT_PASSWORD`. Compose tries to substitute them **from your host shell env**, sees they’re not set, and warns.

### Easiest fix (since you chose host `mc`)

You can simply **remove `minio-init`** completely from compose (recommended, since you’re creating the bucket from your Mac).

If you want to keep `minio-init`, then change `$VAR` to `$$VAR`:

```yaml
command: >
  "
  mc alias set local http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD &&
  mc mb --ignore-existing local/apm-backups &&
  mc ls local &&
  mc ls local/apm-backups
  "
```

✅ `$$VAR` prevents Compose substitution and lets the container shell expand the env vars at runtime.

---

## Fix 3 — Put MinIO on the same network

Right now your `minio` service has no `networks:` block. Add:

```yaml
  minio:
    ...
    networks:
      - backup-net
```

Same for `minio-init` if you keep it.

---

## Fix 4 — Remove `version:` (optional cleanup)

Docker Compose v2 ignores it; safe to remove to avoid the warning.

---

## Run again

From project root:

```bash
docker compose -f docker/docker-compose.backup.yml build
docker compose -f docker/docker-compose.backup.yml up -d
```

Quick checks:

```bash
docker exec -it db pgbackrest --version
docker exec -it pgbackrest pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=apm info
```

If you paste your current `backup/pgbackrest.conf`, I’ll also verify it has the **S3 repo1 (minio:9000)** + **posix repo2 (hot)** settings and the correct `pg1-path`.

Reference: [https://hub.docker.com/u/pgbackrest](https://hub.docker.com/u/pgbackrest)
