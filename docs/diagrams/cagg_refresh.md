# Continuous aggregate refresh flow

```mermaid
flowchart LR
  Raw[Hypertable observability_apirequest] -->|time_bucket, aggregates| CAGG[CAGG apirequest_hourly/daily]
  Policy[Refresh policy] -->|scheduled jobs| CAGG
  CAGG --> Dashboards[Queries / dashboards]
```
