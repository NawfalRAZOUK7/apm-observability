# Backup Schedule (Hot/Cold)

## Overview
- Hot storage: MinIO bucket `pgbackrest`
- Cold storage: MinIO bucket `pgbackrest-cold` (future: AWS S3 Glacier/Deep Archive)
- Encryption at rest: enabled via `PGBACKREST_CIPHER_PASS`

## Retention Policy
- repo1 (hot):
  - `repo1-retention-full=2`
  - `repo1-retention-diff=7`
- repo2 (cold):
  - `repo2-retention-full=12`

## Schedule (UTC)
- Hourly: incremental backup to repo1
- Daily 01:00: differential backup to repo1
- Weekly Sunday 01:05: full backup to repo1
- Monthly first Sunday 02:00: full backup to repo2

## Notes
- `pgbackrest check` validates repo1 (WAL-enabled hot storage) only; repo2 is cold storage with no WAL.
- Validate repo2 by running `pgbackrest info` and periodic `pgbackrest --stanza=apm --repo=2 --type=full backup`.
- Encryption passphrase is supplied via:
  - `PGBACKREST_REPO1_CIPHER_PASS`
  - `PGBACKREST_REPO2_CIPHER_PASS`
- Generate a local pass with:
  - `scripts/gen_pgbackrest_cipher_pass.sh`

## Restore Runbook (Scratch DB)
- Stop the app and connect to a scratch Postgres instance (or a new container).
- Restore from repo1:
  - `pgbackrest --stanza=apm restore --type=full --repo=1`
- Validate:
  - `psql -h <scratch_host> -U <user> -d <db> -c "\\dt"`
  - Optional: run a minimal app health check against the scratch DB.

## Task 4 Status
- Status: done for single-machine LAN setup.

## Next Steps (Production Hardening)
- Decide how to store `PGBACKREST_CIPHER_PASS` securely (local `.env` vs secret manager).
- Confirm the scheduler is running on the control node (`pgbackrest-cron` logs/uptime) and adjust timezone if needed.
- Add monitoring/alerting for failed backups (cron mail, webhook, or log shipping).
- Run a restore drill (restore to a scratch DB) to validate recoverability.
- If/when moving to AWS: switch repo2 endpoint to S3 + Glacier/Deep Archive class and re-test.
