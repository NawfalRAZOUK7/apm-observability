# SLO-as-code

Service-Level Objectives are declared once, in
[`apm-observability.slo.yaml`](apm-observability.slo.yaml), and the Prometheus
artifacts are **generated** from that spec with [Sloth](https://sloth.dev):

- SLI recording rules,
- error-budget and burn-rate recording rules,
- multi-window, multi-burn-rate alerts (page + ticket severities).

Writing objectives declaratively — instead of hand-crafting burn-rate PromQL —
keeps the objective, its error budget, and its alerts consistent and reviewable
in one place.

## The SLOs

| SLO | Objective | SLI |
|---|---|---|
| `requests-availability` | 99.9% / 30d | non-5xx share of HTTP responses (`django_http_responses_total_by_status_total`) |
| `ingest-latency` | 99.0% / 30d | ingestion requests < 500ms (`apm_ingest_latency_seconds`) |

## Generate the rules

```bash
make slo-generate        # writes slo/rules.gen.yml
# or directly:
sloth generate -i slo/apm-observability.slo.yaml -o slo/rules.gen.yml
```

CI (`.github/workflows/slo.yml`) validates the spec and regenerates the rules on
every change to `slo/`, publishing `rules.gen.yml` as an artifact.

## Activate in Prometheus

Add the generated file to Prometheus `rule_files:` (and reload):

```yaml
rule_files:
  - /etc/prometheus/rules/slo.rules.yml   # = slo/rules.gen.yml
```

The generated alerts (`APMRequestsAvailability`, `APMIngestLatency`) then flow
through Alertmanager into the notification sink and incident workflow like any
other alert. `rules.gen.yml` is a build artifact and is gitignored — regenerate
it rather than editing by hand.
