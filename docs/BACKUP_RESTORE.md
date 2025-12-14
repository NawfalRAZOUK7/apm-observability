# Backups & Restore (pgBackRest + MinIO)

Goal: scheduled S3-compatible backups with pgBackRest and a proven restore path. Stack: TimescaleDB, MinIO, pgBackRest (stanza `apm`).

## Components

- `docker/docker-compose.backup.yml`: backup stack (db, minio, pgbackrest, cron).
- `docker/backup/pgbackrest.conf`: pgBackRest config targeting MinIO bucket `pgbackrest`.
- `docker/backup/restore-example.sh`: sample script to wipe DB volume, restore, and restart.

## Quick start

1. Bring up services (db + MinIO + pgBackRest + cron):
   ```sh
   docker compose -f docker/docker-compose.backup.yml up -d minio minio-mc db pgbackrest pgbackrest-cron
   ```
2. Run a manual full backup (first time):
   ```sh
   docker compose -f docker/docker-compose.backup.yml run --rm pgbackrest \
     pgbackrest --stanza=apm --type=full backup
   ```
3. Check backup inventory:
   ```sh
   docker compose -f docker/docker-compose.backup.yml run --rm pgbackrest pgbackrest info
   ```

## Scheduling

- Cron service runs a full backup daily at 03:00 UTC: `pgbackrest --stanza=apm --type=full backup`.
- Health check job runs every 30 minutes: `pgbackrest --stanza=apm check`.
- Adjust the cron expressions in `pgbackrest-cron` command inside `docker-compose.backup.yml` if needed.

## Retention

- `repo1-retention-full=7` keeps the last 7 full backups in the MinIO bucket. Adjust in `docker/backup/pgbackrest.conf`.

## Restore (example)

You can destroy the DB volume and restore the latest backup:

```sh
./docker/backup/restore-example.sh
```

Manual flow (if you prefer step-by-step):

```sh
docker compose -f docker/docker-compose.backup.yml stop db
# remove the DB volume if you want a clean restore
DB_VOL=apm-observability_db_data_backup
docker volume rm "$DB_VOL"
# recreate services
docker compose -f docker/docker-compose.backup.yml up -d minio minio-mc db pgbackrest
# restore into the fresh volume
docker compose -f docker/docker-compose.backup.yml run --rm pgbackrest \
  pgbackrest --stanza=apm --delta --type=default restore
# start database
docker compose -f docker/docker-compose.backup.yml up -d db
# verify
docker compose -f docker/docker-compose.backup.yml exec db psql -U apm -d apm -c 'select now();'
```

## Configuration notes

- MinIO auth defaults to `minioadmin` / `minioadmin`. Set `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` env vars to change.
- Database auth defaults to `apm` / `apm`. Update `docker/backup/pgbackrest.conf` if you change DB credentials.
- TLS to MinIO is disabled (`repo1-s3-verify-tls=n`) for local use. Enable TLS in MinIO and flip this to `y` for real deployments.

## WAL archiving (optional)

The current setup captures full backups. To add point-in-time recovery via WAL:

1. Enable WAL archiving on the database (requires restart):
   ```sql
   ALTER SYSTEM SET wal_level = 'replica';
   ALTER SYSTEM SET archive_mode = 'on';
   ALTER SYSTEM SET archive_command = 'pgbackrest --stanza=apm archive-push %p';
   ALTER SYSTEM SET archive_timeout = '60s';
   ```
2. Restart the db service in the backup compose stack so the settings take effect.
3. Verify WALs flow with `pgbackrest info` and MinIO object listings.

## Verification checklist

- `pgbackrest info` shows completed full backups in repo1 (MinIO).
- Destroying the DB volume and running the restore script brings the database back up.
- Optional: after enabling WAL archiving, create data, force WAL switch (`select pg_switch_wal();`), confirm new WAL uploads, and run a restore.
