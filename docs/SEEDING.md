# Seeding with Faker

## Overview
This project includes a Django management command to seed `ApiRequest` rows with realistic,
repeatable data. It supports two modes:
- ORM (default): fast, direct inserts.
- API (`--via-api`): posts to `/api/requests/ingest/` to exercise the full pipeline.

Default data shape matches the existing API model and scripts:
- Services: `api`, `web`, `auth`
- Endpoints: `/health`, `/login`, `/orders`, `/home`, `/search`

## Install
Faker is included in `requirements.txt`:
```
pip install -r requirements.txt
```

## Basic usage
```
python manage.py seed_apirequests --count 5000 --days 7
```

Deterministic data (repeatable runs):
```
python manage.py seed_apirequests --count 2000 --days 3 --seed 123
```

Custom window:
```
python manage.py seed_apirequests --start 2025-12-01 --end 2025-12-14
```

Custom services and endpoints:
```
python manage.py seed_apirequests --services api,web --endpoints /health,/home
```

Validate payloads with the serializer:
```
python manage.py seed_apirequests --count 1000 --validate
```

## API mode (ingest endpoint)
```
python manage.py seed_apirequests --via-api --count 1000 --days 2 --base-url https://127.0.0.1:8443 --insecure
```

Notes:
- `--via-api` respects `APM_INGEST_MAX_EVENTS` by chunking the payload.
- `--insecure` disables TLS verification for local HTTPS (similar to curl `-k`).

## Safety (truncate)
To delete all `ApiRequest` rows before seeding:
```
python manage.py seed_apirequests --truncate --confirm-truncate yes
```
This is destructive and intended for dev/demo only.

## Docker usage (app container)
```
docker compose -p apm-app \
  --env-file docker/.env.ports \
  --env-file docker/.env.ports.localdev \
  --env-file docker/cluster/.env.cluster \
  -f docker/cluster/docker-compose.app.yml \
  exec -T web python manage.py seed_apirequests --count 2000 --days 5
```

## Post-seed refresh (Timescale)
After seeding, refresh CAGGs so analytics endpoints see fresh data:
```
python manage.py refresh_apirequest_hourly
python manage.py refresh_apirequest_daily
```

## Smoke checks
Use the API endpoints or the existing script:
```
scripts/step5_test.sh
```

## Helper script
A convenience wrapper is available:
```
scripts/seed_faker.sh --count 5000 --days 7
```
