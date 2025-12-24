# Grafana + Prometheus + Timescale (APM Observability)

This setup adds Prometheus + Grafana for infrastructure and app metrics while keeping TimescaleDB as the primary datastore.
Designed for your **cluster docker** layout (DATA / CONTROL / APP).

## What runs where

- **CONTROL node**: Prometheus + Grafana + node-exporter
- **DATA node**: postgres-exporter (Timescale metrics)
- **APP node**: Django `/metrics` (via django-prometheus)

## Services added

- Prometheus (`:9090`) — scrapes metrics targets
- Grafana (`:3000`) — dashboards + data sources (Prometheus + Timescale)
- postgres-exporter (`:9187`) — DB metrics from Timescale
- node-exporter (`:9100`) — host metrics (control node)

## Metrics targets (LAN defaults)

- Django metrics: `http://APP_NODE_IP:28000/metrics`
- Postgres exporter: `http://DATA_NODE_IP:9187/metrics`
- Node exporter: `http://CONTROL_NODE_IP:9100/metrics`

> Update `docker/monitoring/prometheus.yml` if IPs/ports change.

## Run (single-host LAN)

Data node:
```
docker compose -p apm-data \
  --env-file docker/.env.ports \
  --env-file docker/.env.ports.localdev \
  --env-file docker/cluster/.env.cluster \
  -f docker/cluster/docker-compose.data.yml up -d --build
```

Control node:
```
docker compose -p apm-control \
  --env-file docker/.env.ports \
  --env-file docker/.env.ports.localdev \
  --env-file docker/cluster/.env.cluster \
  -f docker/cluster/docker-compose.control.yml up -d --build
```

App node (if not already running):
```
docker compose -p apm-app \
  --env-file docker/.env.ports \
  --env-file docker/.env.ports.localdev \
  --env-file docker/cluster/.env.cluster \
  -f docker/cluster/docker-compose.app.yml up -d --build
```

## Grafana access

- URL: `http://CONTROL_NODE_IP:3000`
- Default login: `admin / change-me`

Update credentials in `docker/cluster/.env.cluster`.

## Dashboards (pre-provisioned)

- **APM Infra Overview** (node-exporter basics: CPU, memory, load, disk)
- **APM Prometheus Targets** (scrape health + durations)

If the dashboards do not appear, restart Grafana on the CONTROL node:
```
docker compose -p apm-control \
  --env-file docker/.env.ports \
  --env-file docker/.env.ports.localdev \
  --env-file docker/cluster/.env.cluster \
  -f docker/cluster/docker-compose.control.yml restart grafana
```

## Notes

- `/metrics` is exempted from SSL redirect in Django to allow Prometheus scraping on LAN HTTP.
- The Timescale datasource is provisioned from env vars (see `docker/monitoring/grafana/provisioning`).
- For multi-node, update IPs and host ports in Prometheus targets.
- On Docker Desktop (macOS), node-exporter runs with a simplified host mount (no `rslave`).
