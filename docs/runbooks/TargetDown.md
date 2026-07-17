# Runbook — TargetDown

**Alert:** `TargetDown` · **Severity:** critical · **Fires when:** a Prometheus
scrape target reports `up == 0` for at least 1 minute.

This runbook is linked automatically from the alert (`runbook_url` annotation)
and surfaced on the incident opened in the notification sink (Phase 9).

## Impact

A monitored component (the Django `web` app, `db`, an exporter, or another
service) is unreachable by Prometheus. If it is `web` or `db`, ingestion and the
API are likely down.

## Diagnose

1. Identify the target from the alert labels: `{{ $labels.job }}` /
   `{{ $labels.instance }}`.
2. Check Prometheus targets: `http://localhost:9090/targets` — confirm which
   target is `DOWN` and read the scrape error.
3. Check the container: `docker compose -f docker/docker-compose.yml ps` and
   `docker compose -f docker/docker-compose.yml logs --tail=100 <service>`.
4. Confirm the service's own health where applicable:
   - web: `curl -fsS http://localhost:8000/api/health/`
   - db: `docker compose exec db pg_isready`

## Recover

- **Container crashed / exited:** `docker compose -f docker/docker-compose.yml up -d <service>`.
- **App unhealthy but running:** inspect logs for a traceback; roll back to the
  last good image tag if a recent deploy caused it (see Track A auto-rollback).
- **DB down:** verify volume + disk, restart `db`; if data is suspect, restore
  from pgBackRest (see `docs/runbooks/` DR procedures / Track B).
- **Network / DNS between services:** confirm all services share `app_network`.

## Verify resolved

- Prometheus target returns to `UP`; `TargetDown` resolves and a `resolved`
  notification is recorded in the sink (`/sink/`).
- Dependent alerts (suppressed by the inhibition rule while the critical fired)
  clear on their own.

## Escalate

If not recovered within the SLA, page the on-call owner (Critical → pager
channel). Capture the incident timeline for the postmortem (Phase 9).
