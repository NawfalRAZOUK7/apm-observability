# Step 11 — Backup scheduling to S3-compatible (MinIO) using pgBackRest (Hot + Cold)

## Goal (Obligatoire)
- Automated backups + retention
- WAL archiving enabled
- Scheduled execution (cron in a container)
- Restore proof: destroy DB volume → restore → queries work again

## Design decision (fixed for this step)
We implement **two repositories**:
- **Repo2 = HOT (chosen)**: local POSIX repo (fast restore, low latency)
- **Repo1 = COLD**: S3-compatible object store (MinIO) for durable storage

Why two repos:
- pgBackRest explicitly supports **multiple repositories** and notes the benefit: local repo for fast restores + remote repo for redundancy. Also, backups/restore operations can be scoped per repo.  
See: `docs/STEP11_PGBACKREST_SETUP.md`.

## Required docs (read in this order)
1) `docs/STEP11_MINIO_SETUP.md` — MinIO (S3-compatible) with bucket auto-create  
2) `docs/STEP11_PGBACKREST_SETUP.md` — pgBackRest install/config (stanza, archiving, repos, retention, schedule)  
3) This file — execution plan + acceptance proof

---

# Execution order (do NOT reorder)

## 1) Add the backup docker stack
### Files to create
- `docker/docker-compose.backup.yml`
- `docker/backup/` (scripts + pgbackrest.conf + cron)
- `docs/STEP11_MINIO_SETUP.md`
- `docs/STEP11_PGBACKREST_SETUP.md`
- `docs/BACKUP_RESTORE.md` (proof steps + evidence)

### Stack must include
- `db` (Timescale/Postgres)
- `minio` (S3-compatible)
- `minio-init` (creates bucket + optional versioning)
- `pgbackrest` (runs backups + expire + info + restore; also runs cron)

**Checkpoint**
- `docker compose -f docker/docker-compose.backup.yml up -d`
- all containers healthy

---

## 2) Bring up MinIO and verify the bucket exists
Follow `docs/STEP11_MINIO_SETUP.md`.

**Checkpoint**
- You can list the bucket (from minio-init or a minio client)
- The bucket exists BEFORE pgBackRest uses it (pgBackRest will not create it automatically)

---

## 3) Configure pgBackRest repositories (Repo1 cold + Repo2 hot)
Follow `docs/STEP11_PGBACKREST_SETUP.md`.

You must have:
- `stanza = apm`
- `pg1-path = <PGDATA mount path>`
- Repo1 (cold): `repo1-type=s3`, endpoint = `minio:9000`, bucket, key/secret, region, and preferably a subpath/prefix
- Repo2 (hot): `repo2-type=posix`, `repo2-path=/var/lib/pgbackrest-hot`

**Checkpoint**
- `pgbackrest --stanza=apm info` works
- repos are visible/configured

---

## 4) Enable WAL archiving in PostgreSQL
This is REQUIRED to backup a running cluster.

### Minimum settings
- `archive_mode=on`
- `archive_command='pgbackrest --stanza=apm archive-push %p'`
- also ensure WAL settings are compatible (e.g., wal_level, max_wal_senders)

**Important Docker note**
`archive_command` runs inside the DB container, so the DB container must be able to execute `pgbackrest`.
Recommended approach:
- Build a small custom DB image that installs `pgbackrest`, or
- Use a Postgres/Timescale image that already includes it (rare), or
- (Less clean) install at container start in an entrypoint script

**Checkpoint**
- after restart, archiving works and `pgbackrest --stanza=apm check` passes

---

## 5) First-time initialization: stanza-create + check
Run once from the pgbackrest container:
- `pgbackrest --stanza=apm stanza-create`
- `pgbackrest --stanza=apm check`

**Checkpoint**
- `check` shows WAL segment archived successfully

---

## 6) Manual backup test (before scheduling)
Do at least one FULL backup to both repos:

- Cold:
  - `pgbackrest --stanza=apm --repo=1 --type=full backup`
- Hot (chosen):
  - `pgbackrest --stanza=apm --repo=2 --type=full backup`

**Checkpoint**
- `pgbackrest info` shows backup sets

---

## 7) Configure retention and expiration (keep last N)
Set policy (example):
- Repo1 cold: keep 7 full backups
- Repo2 hot: keep 2 full backups
(You can also set archive retention.)

Then ensure `expire` runs on schedule:
- `pgbackrest --stanza=apm --repo=1 expire`
- `pgbackrest --stanza=apm --repo=2 expire`

**Checkpoint**
- no warnings about unlimited growth
- `info` shows retention policy applied

---

## 8) Add scheduling (cron container)
Use cron inside `pgbackrest` container to run:
- hourly incremental (repo2 hot)
- every 6 hours differential (repo2 hot)
- daily full (repo1 cold + repo2 hot)
- expire daily (both)

**Checkpoint**
- logs show backups run automatically at the expected times

---

## 9) Restore proof (Obligatoire)
### 9.1 Create/seed data
- Ingest sample API requests (your existing ingestion endpoint) OR seed with faker
- Record evidence:
  - counts from DB (`SELECT count(*)...`)
  - and/or API responses

### 9.2 Take a fresh backup
- run a full backup (repo2 hot at minimum)
- run `pgbackrest info` and save output

### 9.3 Destroy DB volume (simulate disaster)
- stop stack
- remove ONLY the Postgres data volume (pgdata)

### 9.4 Restore
Preferred restore for demo:
- Restore from **Repo2 hot** (fast):
  - `pgbackrest --stanza=apm --repo=2 restore`

Backup/DR demonstration:
- Also show restore from Repo1 cold if required:
  - `pgbackrest --stanza=apm --repo=1 restore`

### 9.5 Verify
- start db
- run DB query checks
- hit `/api/requests/`, `/hourly/`, `/daily/` endpoints

**Acceptance**
- You can destroy DB volume, restore, and queries work again.
