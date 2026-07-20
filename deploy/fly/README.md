# Public demo on Fly.io

A slim, always-on-ish public demo: the Django/DRF app + dashboard, backed by a
TimescaleDB running as a second Fly app. Scales to zero when idle so it stays
within the free allowance. This is a *demo*, not the full LGTM stack.

Result: a public URL like `https://apm-observability-demo.fly.dev/dashboard/`.

## Prerequisites

- A [Fly.io](https://fly.io) account and `flyctl` installed (`fly auth login`).
- The app requires **PostgreSQL + TimescaleDB** (the platform's only backend).

## 1. Database — TimescaleDB on Fly

Run the project's Timescale image as its own Fly app with a persistent volume:

```bash
fly apps create apm-demo-db
fly volumes create pgdata --app apm-demo-db --size 1 --region cdg

# Launch timescale/timescaledb with the volume mounted at the PG data dir.
# (Simplest: a tiny fly.toml for the DB using image = "timescale/timescaledb:2.17.2-pg16",
#  mount pgdata → /var/lib/postgresql/data, and set POSTGRES_PASSWORD as a secret.)
fly secrets set --app apm-demo-db POSTGRES_PASSWORD=<db-password> POSTGRES_USER=apm POSTGRES_DB=apm
```

> Alternative: use a managed **Timescale Cloud** free trial and skip running your
> own DB app — just point the secrets below at its connection string.

## 2. App — deploy from this config

```bash
cd deploy/fly
fly launch --no-deploy --copy-config --name apm-observability-demo

# Secrets (never commit these):
fly secrets set \
  DJANGO_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')" \
  POSTGRES_HOST="apm-demo-db.internal" \
  POSTGRES_USER="apm" \
  POSTGRES_PASSWORD="<db-password>"

fly deploy
```

The container entrypoint waits for the DB, runs migrations, and starts Gunicorn
on `:8000`; Fly's edge terminates TLS and forwards to it.

## 3. Seed some data so the dashboard isn't empty

```bash
fly ssh console -C "python manage.py seed_apirequests --count 2000 --days 2"
fly ssh console -C "python manage.py demo_e2e --traces 25"   # tenant + traces + a test alert
```

Open `https://<your-app>.fly.dev/dashboard/`.

## Notes & caveats

- **Slim by design.** Prometheus/Grafana/Tempo/Loki are not deployed here — the
  first-party dashboard and REST API are. For the full stack, use `make demo`
  locally or the Helm chart on Kubernetes.
- **Cost.** `auto_stop_machines` scales the app to zero when idle; the DB app +
  volume are the main always-on cost. Keep the volume small (1 GB) for a demo.
- **Security.** This is a public demo with seeded data — don't put anything real
  in it. Secrets live only in `fly secrets`, never in `fly.toml`.
- Once live, add the URL to the top of the main [README](../../README.md).
