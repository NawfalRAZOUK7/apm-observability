# OpenTelemetry Collector: the front-door pattern

The platform ingests **native OTLP** directly (`/v1/traces`, `/v1/metrics`,
`/v1/logs` over HTTP + gRPC), so any OpenTelemetry SDK can point at it unchanged.
In most real deployments, though, you don't want every service talking to the
backend directly — you put an **OpenTelemetry Collector** in front as an edge/agent
tier that batches, retries, and (optionally) samples before forwarding.

```
service A ─┐
service B ─┼─▶ OTel Collector (edge) ─▶ APM platform  /v1/traces|metrics|logs
service C ─┘        batch, retry,          (tenant resolved from API key)
                    memory_limiter
```

## Two collectors, two jobs

| Config | Role |
|---|---|
| [`docker/monitoring/otel-collector-config.yaml`](../docker/monitoring/otel-collector-config.yaml) | In-stack: receives the Django app's traces and forwards them to **Tempo**. |
| [`docker/otel-collector/edge-collector.yaml`](../docker/otel-collector/edge-collector.yaml) | Reference **front-door**: receives OTLP from any service and forwards traces/metrics/logs into the platform's ingestion API. |

## Running the edge collector

The platform authenticates ingestion with a tenant API key
(`Authorization: Api-Key <key>`), so the collector injects that header. Mint a key
first (`make demo-features` seeds one, or `manage.py seed_tenant`):

```bash
export APM_PLATFORM_OTLP_ENDPOINT=http://localhost:8000   # or your https host
export APM_INGEST_API_KEY=<tenant-api-key>

otelcol-contrib --config docker/otel-collector/edge-collector.yaml
```

Now point any OTel SDK at the collector (`OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`)
and its telemetry flows SDK → collector → platform, tenant-scoped by the key.

## Why this matters

- **Decoupling** — services emit vanilla OTLP to a local collector; only the
  collector holds the platform endpoint + credential.
- **Resilience** — batching and retry live in the collector, not every service.
- **Portability** — swapping the backend is a collector-exporter change, not a
  redeploy of every service.
