# Backup & Restore Proof Steps

## 1. Backup Stack Setup

- Ensure all containers (`db`, `minio`, `minio-init`) are up and healthy using:
  ```sh
  docker compose -f docker/docker-compose.backup.yml up -d
  ```
- Confirm MinIO bucket exists (via minio-init or MinIO console).

## 2. WAL Archiving

- Confirm `archive_mode=on` and `archive_command` in Postgres.
- Check `pgbackrest --stanza=apm check` passes (from pgbackrest container):
  ```sh
  ./docker/backup/pgbackrest_mode.sh check
  ```

## 3. Manual Backup

- Run full backup to both repos:
  ```sh
  ./docker/backup/pgbackrest_mode.sh backup --repo=1 --type=full
  ./docker/backup/pgbackrest_mode.sh backup --repo=2 --type=full
  ./docker/backup/pgbackrest_mode.sh info
  ```
- Confirm backup sets are visible.

## 4. Retention/Expiration

- Run:
  ```sh
  ./docker/backup/pgbackrest_mode.sh expire --repo=1
  ./docker/backup/pgbackrest_mode.sh expire --repo=2
  ```
- Confirm retention policy is applied.

## 5. Restore Proof

- Ingest or seed data, record evidence (counts, API responses).
- Take a fresh backup.
- Stop stack, remove only the Postgres data volume.
- Restore from hot repo:
  ```sh
  ./docker/backup/pgbackrest_mode.sh restore --repo=2
  ```
- Start db, verify data and endpoints.

## Acceptance

- You can destroy DB volume, restore, and queries work again.

# Backups & Restore (WAL-G + MinIO)

## Quick start

1. Bring up services (db + MinIO + WAL-G):
   ```sh
   docker compose -f docker/docker-compose.backup.yml up -d minio minio-mc db walg
   ```
2. Run a manual full backup:
   ```sh
   ./docker/backup/backup.sh
   ```
3. Restore the latest backup:
   ```sh
   ./docker/backup/restore.sh
   ```

## Configuration notes

- MinIO auth defaults to `minioadmin` / `minioadmin`. Set `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` env vars to change.
- Database auth defaults to `apm` / `apm`. Update your .env files if you change DB credentials.
- WAL-G settings are applied via docker/initdb/002_walg_settings.sql.

## PITR (Point-in-Time Recovery)

To restore to a specific point in time, use:

```sh
docker compose -f docker/docker-compose.backup.yml run --rm walg wal-g backup-fetch /var/lib/postgresql/data LATEST --target-time="YYYY-MM-DDTHH:MM:SSZ"
```

## Verification checklist

- WAL-G backup-push uploads to MinIO bucket `dbbackup/walg`.
- Destroying the DB volume and running the restore script brings the database back up.
- PITR works as expected when using the --target-time option.
