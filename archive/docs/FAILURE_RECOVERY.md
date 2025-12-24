# Failure Simulation & Recovery (Task 6)

## Scope
This runbook validates failure handling and recovery for the current single-machine LAN setup.
It is designed to scale to a multi-node LAN later (DATA/CONTROL/APP split).

## Prerequisites
- Cluster stacks are running:
  - DATA: `docker/cluster/docker-compose.data.yml`
  - CONTROL: `docker/cluster/docker-compose.control.yml`
  - APP: `docker/cluster/docker-compose.app.yml`
- Recent backups exist (repo1 hot at minimum):
  - `pgbackrest --stanza=apm info`
- Seed tooling is available (Task 5):
  - `python manage.py seed_apirequests ...`
- Local Python environment is available (scripts prefer `.venv/bin/python` if present).

## Quick Start (Scripts)
All scripts live under `scripts/drills/`:
- `00_baseline.sh` (seed + evidence)
- `01_primary_restore.sh` (primary volume loss + restore)
- `02_failover_replica.sh` (manual failover)
- `03_minio_outage.sh` (MinIO outage simulation)

Example:
```
scripts/drills/00_baseline.sh
CONFIRM=YES scripts/drills/01_primary_restore.sh
CONFIRM=YES scripts/drills/02_failover_replica.sh
scripts/drills/03_minio_outage.sh
```

Container name overrides (if yours differ):
```
APP_WEB_CONTAINER=apm-app-web-1
DATA_DB_CONTAINER=apm-data-db-1
CONTROL_PGBR_CONTAINER=apm-control-pgbackrest-1
CONTROL_MINIO_CONTAINER=apm-control-minio-1
```

## Scenario A — Primary Volume Loss + Restore (pgBackRest)
Goal: prove you can recover from a primary data loss using repo1 (hot).

Steps:
1) Stop primary DB container.
2) Wipe the primary data volume (single-machine safe variant).
3) Restore from repo1 using `pgbackrest restore`.
4) Start DB and re-check API endpoints.

Script:
```
CONFIRM=YES scripts/drills/01_primary_restore.sh
```

Success criteria:
- DB starts and passes health checks.
- API endpoints return 200.
- Row counts are close to baseline (RPO window).

## Scenario B — Manual Failover to Replica
Goal: promote a replica and point the app to it.

Steps:
1) Stop primary DB.
2) Promote replica (`pg_promote()`).
3) Repoint app to replica and restart the web container.

Script:
```
CONFIRM=YES scripts/drills/02_failover_replica.sh
```

Success criteria:
- App writes succeed on new primary.
- `check_cluster_dbs` reports writes on new primary.

Cleanup (single-machine):
- Stop the promoted replica.
- Start the original primary container.
- Rebuild replication if needed (not automated in this drill).

## Scenario C — MinIO Outage (Backup Repo)
Goal: ensure DB remains up and backups resume after MinIO returns.

Steps:
1) Stop MinIO on CONTROL node.
2) Observe that `pgbackrest check` fails (expected).
3) Restart MinIO and re-run `pgbackrest check`.

Script:
```
scripts/drills/03_minio_outage.sh
```

Success criteria:
- DB stays online while MinIO is down.
- `pgbackrest check` passes after MinIO restarts.

## Evidence to Save
- Baseline row count from `observability_apirequest`
- `pgbackrest info` before and after
- HTTP 200 from:
  - `/api/health/`
  - `/api/requests/kpis/`
  - `/api/requests/top-endpoints/`
- Logs or output of the drill scripts

## Notes (Single-Machine LAN)
- Recovery uses repo1 (hot). Repo2 is cold storage (full backups only).
- Failover in single-machine mode is functional but not a substitute for multi-node HA.
