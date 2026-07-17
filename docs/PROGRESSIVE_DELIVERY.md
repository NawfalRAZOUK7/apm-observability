# Progressive delivery (Phase 17)

Argo Rollouts replaces the all-at-once Deployment with a **canary** that shifts
traffic in steps, running **metric-based analysis** between steps. If the canary
breaches the SLO, the rollout **auto-aborts and rolls back** — no human needed.

## How it works

1. Install the controller: `infra/terraform/modules/argo_rollouts` (or
   `helm install argo-rollouts argo/argo-rollouts -n argo-rollouts`).
2. Deploy the app with `rollout.enabled=true` (the chart then renders a
   `Rollout` + `AnalysisTemplate` instead of a `Deployment`).
3. Each new image tag triggers the canary:

```
setWeight 20 → pause 60s → analysis
setWeight 50 → pause 60s → analysis
setWeight 80 → pause 60s → analysis
→ 100% (promoted)   |   analysis fails → abort + rollback
```

## The analysis (drives promotion)

The `AnalysisTemplate` queries the app's own Prometheus SLIs:

- **success-rate:** `≥ 95%` non-5xx over 2m (`successRateThreshold`)
- **p95 latency:** `≤ 1s` (`latencyP95Threshold`)

Both must hold at every check (`count` × `interval`); a single breach past
`failureLimit` aborts the rollout. Tune these in `values.yaml` under
`rollout.analysis`. The queries reuse the same metrics as the SLO burn-rate
alerts, so promotion criteria and paging criteria stay consistent.

**Canary-scoped, not Service-scoped.** The Rollout passes the canary's
`rollouts-pod-template-hash` into the analysis, and the queries filter on a
matching `rollouts_pod_template_hash` metric label — so the analysis measures
**only the new pods**, not the whole Service (otherwise a bad canary at 20%
weight might not move the aggregate, and a sick *stable* version could abort a
good canary). That label reaches the metrics via the chart's **PodMonitor**, so
per-canary analysis requires the Prometheus Operator (kube-prometheus-stack) and
`metrics.podMonitor.enabled=true`.

## Database migrations

Migrations run as a **Helm `post-install`/`pre-upgrade` Job**
(`templates/migrate-job.yaml`), so the schema is current *before* the app (or a
canary) starts — never an initContainer, which would run per-replica and race
(Django migrations aren't concurrency-safe). Under ArgoCD it maps to a `PreSync`
hook. Disable with `migrations.enabled=false` if you run them out of band.

Because a Helm `pre-upgrade` hook fires *before* the new ConfigMap/Secret are
applied, the Job would otherwise read the **previous** revision's config. The
Job therefore injects the DB connection (`POSTGRES_HOST/PORT/DB/USER`,
`DB_SSLMODE`) directly from the current chart values, overriding `envFrom`, so
migrations always target the new database. **Residual edge:** the DB *password*
still comes from the Secret, so rotating the password in the *same* upgrade that
migrates would use the old value — rotate the password in a separate step, or
run migrations out of band (`--no-hooks`) for that upgrade.

## CI/CD

`scripts/deploy/deploy-k8s.sh` is rollout-aware: set `ROLLOUT=1` and it deploys
via the canary and watches `kubectl argo rollouts status`, undoing on failure.
Wire `ROLLOUT=1` into the `deploy-production` job once the controller is installed.

## Try it locally

```bash
kubectl argo rollouts get rollout apm-apm-observability -n apm --watch
# ship a bad build and watch the canary abort on the success-rate metric
```
