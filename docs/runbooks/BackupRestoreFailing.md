# Runbook — BackupRestoreVerificationFailing

**Alert:** `BackupRestoreVerificationFailing` · **Severity:** critical · **Fires
when:** `apm_backup_restore_success == 0` (the automated restore verification
drill failed).

This is a *latent* failure — nothing is down right now, but the backups may not
be restorable, which is a serious DR risk. Treat with urgency.

## Diagnose

1. Read the latest verification output: re-run it locally with verbose logs —
   `scripts/drills/verify_restore.sh` — or open the last `dr-verify` workflow run
   and its `dr-verify-metrics` artifact.
2. Check which stage failed (the script logs `[1/4]`…`[4/4]`):
   - **check** failed → pgBackRest config / repo / archiving problem.
   - **info / no backups** → no backup exists; the backup job may be broken.
   - **restore** failed → repo corruption or MinIO access issue.
   - **consistency** failed → restored cluster incomplete (missing WAL).
3. Inspect the repo: `pgbackrest --stanza=apm info` and MinIO availability.

## Recover

- **Archiving broken:** verify `archive_command` and pgBackRest TLS/mTLS certs;
  fix, then force a fresh full backup: `pgbackrest --stanza=apm --type=full backup`.
- **MinIO unreachable / bucket missing:** restore MinIO (see `03_minio_outage.sh`
  drill), re-run `minio-init`, then re-take a backup.
- **Repo corruption:** take a new full backup to a clean repo path; investigate
  the corrupt one out-of-band.
- Re-run `verify_restore.sh`; confirm `apm_backup_restore_success` returns to 1.

## Verify resolved

- The DR dashboard (`APM — Disaster Recovery`) shows restore = PASSING, RPO
  within target, RTO acceptable, and "Last verified" recent.

## Escalate

If backups cannot be made restorable, escalate immediately — the system is
running without a proven recovery path.
