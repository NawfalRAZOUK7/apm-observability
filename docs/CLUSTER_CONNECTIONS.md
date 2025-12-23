# Cluster Connections (Task 2)

## Goals
- Ensure the backend can read/write each DB node in the cluster.
- Define a clear role for every connection (primary write, replica read, backup, etc.).

## Current LAN setup note
- The validation in this repo is done on a single-machine LAN setup (all nodes share one host).
- If you move to separate machines, update `docker/cluster/.env.cluster` with real node IPs and re-run the checks.

## Connection roles
- App backend -> DB primary: writes, migrations, admin operations.
- App backend -> DB replicas: read-only queries (Django router).
- APM agents -> App API: ingest metrics/traces.
- Control node pgBackRest client -> Data node pgBackRest server (TLS 8432): backup commands.
- Data node Postgres -> Control node MinIO (HTTPS 9000): WAL archive + backup storage.

## DB role separation (Scenario A)
- `apm_writer`: write access for ingest + CRUD routes.
- `apm_reader`: read-only access for analytics/Grafana/API reads.
- `default` (admin user): migrations and admin tasks.
- Credentials come from `POSTGRES_APP_USER/PASSWORD` and `POSTGRES_READONLY_USER/PASSWORD`.
- Routing defaults:
  - Safe methods (GET/HEAD/OPTIONS) -> replicas/reader.
  - Unsafe methods -> primary/writer.
  - Read-after-write pinned to primary for `READ_AFTER_WRITE_TTL` seconds.

## How this repo maps roles
- Primary host: `CLUSTER_DB_PRIMARY_HOST` (host or host:port)
- Replica hosts: `CLUSTER_DB_REPLICA_HOSTS` (comma list, host or host:port)
- Probe list (optional): `CLUSTER_DB_HOSTS`
- Port defaults come from `POSTGRES_PORT` in the app container.

The router is enabled automatically when replicas are set:
`apm_platform/db_router.py` routes reads to replicas and writes to primary.

## Task 2 TODO
- Fill `CLUSTER_DB_REPLICA_HOSTS` with actual replica nodes in `docker/cluster/.env.cluster`.
- Run the probe from the backend container:
  - `python manage.py check_cluster_dbs`
- Validate read routing (reads hit replicas, writes hit primary).
- Document any TLS/firewall requirements between nodes.

## Replica setup plan (streaming replication)
This project uses a single DB service today. To add replicas, use PostgreSQL
streaming replication on separate machines/containers.

### 1) Primary node (DATA)
Objective: accept writes and stream WAL to replicas.
- Ensure port 5432 is reachable from replica nodes.
- Create a replication user (run on primary):
  - `CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'change-me';`
- Add `pg_hba.conf` entry to allow replica IPs:
  - `host replication replicator <replica_ip>/32 md5`
- Recommended primary settings (can be added to `docker/cluster/docker-compose.data.yml` command):
  - `wal_level=replica`
  - `max_wal_senders=10`
  - `max_replication_slots=10`
  - `wal_keep_size=256MB` (or higher if network is slow)

### 2) Replica node(s)
Objective: read-only queries, kept in sync via WAL.
- Provision a new DB host or container for each replica.
- Initialize data directory from primary with `pg_basebackup`:
  - `pg_basebackup -h <primary_ip> -U replicator -D /var/lib/postgresql/data -Fp -Xs -P -R`
  - `-R` writes `standby.signal` + `primary_conninfo`.
- Set read-only mode (replicas should not accept writes):
  - `hot_standby=on` (default on most builds)
- Start the replica and confirm it stays in recovery.

### 3) Verification
- On primary:
  - `SELECT application_name, client_addr, state, sync_state FROM pg_stat_replication;`
- On replica:
  - `SELECT pg_is_in_recovery();` should be `true`.

### 4) App routing + probe
Objective: reads go to replicas, writes stay on primary.
- Set in `docker/cluster/.env.cluster`:
  - `CLUSTER_DB_PRIMARY_HOST=<primary_ip>:<port>`
  - `CLUSTER_DB_REPLICA_HOSTS=<replica1_ip>:<port>,<replica2_ip>:<port>`
- Rebuild/restart the app container so it loads the router in `apm_platform/db_router.py`.
- Run the probe:
  - `python manage.py check_cluster_dbs`
