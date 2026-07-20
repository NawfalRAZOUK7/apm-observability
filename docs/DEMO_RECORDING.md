# Recording the demo GIF

A short (15–30s) looping GIF at the top of the README is the single highest-signal
addition to the repo — it shows the platform *working* in the time a reviewer
actually spends. This is the recipe.

## What to capture

Two clips are worth having:

1. **Dashboard coming alive** — bring the stack up, drive traffic, and show the
   dashboard tabs update (service map drawing, KPIs moving, an incident appearing).
2. **Canary auto-rollback** (the money shot) — a bad rollout being aborted by the
   Prometheus analysis, on the Argo Rollouts dashboard.

Keep each clip to one idea. The README embeds clip 1; link clip 2 below it.

## Tooling

Pick one screen-to-GIF recorder:

| Tool | Platform | Notes |
|---|---|---|
| [Kap](https://getkap.co/) | macOS | Simplest; exports GIF/MP4 directly. |
| [Peek](https://github.com/phw/peek) | Linux | Region capture → GIF. |
| [`vhs`](https://github.com/charmbracelet/vhs) | all | Scriptable *terminal* GIFs (great for the `make demo` sequence). |
| ScreenToGif | Windows | Editor + capture. |

For the terminal portion, `vhs` gives clean reproducible GIFs from a script — see
the `.tape` example below.

## Steps (dashboard clip)

```bash
# 1. Bring up the full single-node stack
make demo

# 2. In a second terminal, seed a tenant + API key, send OTLP traces, fire an alert
make demo-features

# 3. Start recording the browser, then drive traffic so charts move
make loadtest          # k6 drives metrics + fires alerts

# 4. Open the dashboard and click through the tabs while traffic flows
#    https://localhost:8443/dashboard/
#    Service Map → Incidents → Anomalies → Traces → Issues → Ask → DORA
```

Record ~20s of the dashboard with traffic flowing, click 2–3 tabs, stop.

## Optimise and embed

```bash
# Trim + downscale for a small, crisp loop (needs ffmpeg + gifsicle)
ffmpeg -i raw.mov -vf "fps=12,scale=1000:-1:flags=lanczos" -loop 0 docs/images/demo.gif
gifsicle -O3 --colors 200 docs/images/demo.gif -o docs/images/demo.gif
```

Keep it **under ~5 MB** so GitHub renders it inline. Then reference it at the top
of the README:

```markdown
![APM Observability demo](docs/images/demo.gif)
```

## Example `vhs` tape (terminal portion)

```
# demo.tape — render with: vhs demo.tape  → outputs demo.gif
Output docs/images/demo-terminal.gif
Set FontSize 18
Set Width 1200
Set Height 700
Type "make demo" Enter
Sleep 8s
Type "make demo-features" Enter
Sleep 6s
Type "curl -sk https://localhost:8443/api/requests/kpis/ | jq" Enter
Sleep 4s
```

## Where the files go

- `docs/images/demo.gif` — the README hero clip.
- `docs/images/canary-rollback.gif` (or `.mp4`) — linked under it.

Both are already covered by the `docs/images/` path the README uses.
