# Screenshot checklist for the report (Chapter 5)

Chapter 5 (`Chap5_Avance.tex`) uses placeholder boxes so the report compiles
without images. To finalize it, capture the screenshots below, save them to
`docs/report/latex/images/` with the exact filename, then in `Chap5_Avance.tex`
uncomment the matching `\includegraphics` line and delete the `\fbox{...}`
placeholder just below it.

Start the stack first: `make demo` (then `make loadtest` in another terminal to
generate traffic so dashboards/traces/alerts are populated).

| Filename | How to capture |
| --- | --- |
| `swagger_ui.png` | Open `http://localhost:8000/api/docs/` — the Swagger UI listing all endpoints. |
| `k6_summary.png` | Run `K6_WEB_DASHBOARD=true make loadtest`; screenshot the live dashboard at `http://localhost:5665` showing p95 latency, `http_req_failed`, and `checks`. If the dashboard is unavailable, use the terminal end-of-test summary as a fallback. |
| `tempo_trace.png` | Grafana `http://localhost:33000` → Explore → Tempo → open a recent trace (waterfall of spans). |
| `loki_logs.png` | Grafana → Explore → Loki → query `{container=~".+"}`; show a JSON log line with `trace_id`. |
| `prometheus_alerts.png` | Prometheus `http://localhost:9090/alerts` during/after `make loadtest`; show `SLOAvailabilityFastBurn` / `HighErrorRate` PENDING or FIRING. |
| `argocd_app.png` | Run `make argocd-up` (needs a local cluster; see `deploy/README.md`), then `make argocd-ui` and log in — capture the `apm-observability` Application `Synced/Healthy`. Optional. |

Tips:
- Use a 16:9 crop; width ~1600px renders cleanly at `0.9\textwidth`.
- Keep the Grafana theme light for print legibility.
- The `argocd_app.png` is optional — if you don't stand up a cluster, leave the
  placeholder or remove that figure from `Chap5_Avance.tex`.
