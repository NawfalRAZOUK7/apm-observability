# Step 11 — pgBackRest setup (Timescale/Postgres) with Repo2 HOT + Repo1 COLD (MinIO)

## What pgBackRest gives us

- Physical backups (full/diff/incr)
- WAL archiving support for consistent restore and PITR
- Backup integrity checks and built-in retention/expiration
- Multiple repositories (hot + cold)

## 1) Installation / availability (Docker context)

In classic Linux installs, pgBackRest creates/uses:

- config directory (e.g., `/etc/pgbackrest/`)
- log directory (e.g., `/var/log/pgbackrest/`)
  and a main config file (e.g., `/etc/pgbackrest/pgbackrest.conf`).

In Docker:

- We mount a config file into the pgbackrest container.
- IMPORTANT: PostgreSQL needs to run `archive_command`, so the **DB container must also have pgbackrest available**.

### Recommendation

Create a small custom DB image:

- Base: your TimescaleDB image
- Install `pgbackrest` via the distro package manager
- Copy/enable config if you keep it inside db container (or mount it)

## 2) Configure repositories (Repo1 COLD = S3/MinIO, Repo2 HOT = local)

Create: `docker/backup/pgbackrest.conf`

Example (adapt paths to your actual mounts):

```ini
[apm]
pg1-path=/var/lib/postgresql/data

[global]
# Useful defaults
log-level-console=info
start-fast=y
process-max=2

# Repo1 = COLD (S3-compatible MinIO)
repo1-type=s3
repo1-s3-endpoint=minio:9000
repo1-s3-bucket=apm-backups
repo1-s3-region=us-east-1
repo1-s3-key=minioadmin
repo1-s3-key-secret=minioadmin123
# recommended: store repo in a subpath inside the bucket
repo1-path=/pgbackrest

repo1-retention-full=7

# Repo2 = HOT (local)
repo2-type=posix
repo2-path=/var/lib/pgbackrest-hot
repo2-retention-full=2
```

## Why `start-fast=y`

By default, pgBackRest can wait for the next checkpoint before starting a backup; `start-fast=y` forces a checkpoint so backups start immediately (good for predictable schedules).

## 3) S3/MinIO repo rules

- The S3 bucket must exist beforehand (pgBackRest will not create it).
- It’s recommended to store the repository in a subpath/prefix inside the bucket.

## 4) Enable WAL archiving in PostgreSQL (required)

Add to Postgres config (or pass via `-c` flags on container start):

```
archive_mode = on
archive_command = 'pgbackrest --stanza=apm archive-push %p'
```

Also ensure WAL settings are compatible (e.g. max_wal_senders, wal_level as needed).

## 5) First-time initialization (run once)

From pgbackrest container:

```
pgbackrest --stanza=apm stanza-create
pgbackrest --stanza=apm check
```

Expected: `check` confirms a WAL segment is successfully stored in the archive.

## 6) Backup commands (manual)

- Full backup (Repo2 HOT):
  - `pgbackrest --stanza=apm --repo=2 --type=full backup`
- Full backup (Repo1 COLD):
  - `pgbackrest --stanza=apm --repo=1 --type=full backup`
- List backups:
  - `pgbackrest info`

## 7) Retention & expiration

pgBackRest expires backups based on retention options (e.g. `repo*-retention-full`).

Run expiration:

```
pgbackrest --stanza=apm --repo=1 expire
pgbackrest --stanza=apm --repo=2 expire
```

## 8) Scheduling (cron)

Backups can be scheduled with cron.

Suggested schedule (example):

- Repo2 HOT:
  - hourly incremental
  - every 6h differential
- Repo1 COLD:
  - daily full
- Expire daily (both repos)

You can implement cron in the pgbackrest container by:

- mounting a crontab file into `/etc/cron.d/pgbackrest`
- starting `cron -f` as container command
- calling scripts that run `pgbackrest backup / expire`

## 9) Restore procedure (proof)

General restore flow:

1. stop postgres
2. empty PGDATA (or delete volume)
3. run `pgbackrest restore`
4. start postgres and verify data

Commands:

- Restore from Repo2 HOT:
  - `pgbackrest --stanza=apm --repo=2 restore`
- Restore from Repo1 COLD:
  - `pgbackrest --stanza=apm --repo=1 restore`

## 10) Performance note (report / advanced discussion)

In production AWS environments, teams may combine pgBackRest with EBS snapshots to massively speed up backup creation and restore. This is out-of-scope for local MinIO, but valuable as an “industry option”.

**pgBackRest factual refs used:**  
- Installation directories + “check installation worked” example: :contentReference[oaicite:2]{index=2}  
- Multiple repositories benefit (local fast restore + remote redundancy): :contentReference[oaicite:3]{index=3}  
- S3 repo rules (bucket must exist; subpath recommended): :contentReference[oaicite:4]{index=4}  
- WAL archiving required for online backups: :contentReference[oaicite:5]{index=5}  
- Retention via `repo*-retention-full`: :contentReference[oaicite:6]{index=6}  
- Cron scheduling mention: :contentReference[oaicite:7]{index=7}  
- Restore flow example (`pgbackrest restore` after cleaning datadir): :contentReference[oaicite:8]{index=8}  
- Performance context (WAL replay + large DB pain; snapshots + pgBackRest idea): :contentReference[oaicite:9]{index=9}  
