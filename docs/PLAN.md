# APM Observability (Django + Timescale) — Implementation Plan

## Step 0 — Bootstrap & repo
- Clean repo structure, venv, dependencies
- Docker Compose: TimescaleDB
- Base settings and run instructions

## Step 1 — Core API (ApiRequest model + CRUD)
- ApiRequest model + migrations
- DRF serializer + ViewSet + routes
- Basic filtering & ordering

## Step 2 — Ingestion endpoint (bulk)
- /api/requests/ingest/ accepts list of events
- Validates + inserts efficiently
- Returns {inserted: X, rejected: Y}

## Step 3 — Timescale hypertable + hourly continuous aggregate
- Convert table to hypertable
- Create hourly cagg + refresh policy
- /api/requests/hourly/ endpoint

## Step 4 — Daily continuous aggregate + endpoint analytics
- Create daily cagg (service+endpoint)
- /api/requests/daily/ endpoint

## Step 5 — Filters + KPIs
- p95 latency, error-rate, top endpoints
- more filters (service, endpoint, method, status range, tags)

## Step 6 — Tests + quality
- ingestion tests, analytics tests
- formatting + linting conventions

## Step 7 — Docker/Deploy + docs
- production dockerfile + compose
- docs + Postman collection
