# Contributing

Thanks for your interest in contributing to APM Observability! This guide covers
the local setup, the quality gates, and the pull-request workflow.

## Development setup

Prerequisites: Python 3.12, Docker + Docker Compose, and (optionally) `make`.

```bash
# 1. Create a virtualenv and install pinned dependencies
python -m venv .venv && . .venv/bin/activate
make install                # pip install -r requirements.txt

# 2. Start PostgreSQL + TimescaleDB (the one and only backend), then run the app
docker compose -f docker/docker-compose.yml up -d db
python manage.py migrate
python manage.py runserver

# 3. Or bring up the full single-node stack in one command
make demo                   # API + Postgres + Prometheus/Grafana/Tempo/Loki/Alertmanager
```

Dependencies are managed with `pip-tools`: edit `requirements.in`, then run
`make compile-deps` to regenerate the pinned `requirements.txt`. Never edit
`requirements.txt` by hand.

## Quality gates (run before pushing)

These mirror the CI pipeline (`.github/workflows/ci.yml`):

```bash
ruff check .                # lint
black --check .             # formatting (run `black .` to fix)
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test       # requires PostgreSQL/TimescaleDB (step 2 above)
```

For data changes, the data-quality gate must pass:

```bash
python manage.py check_data_quality --fail-on-empty
```

## Commit & PR conventions

- Branch off `main`: `feat/<short-topic>`, `fix/<short-topic>`, `docs/<short-topic>`.
- Prefer [Conventional Commits](https://www.conventionalcommits.org/) messages,
  e.g. `feat(tracing): add OpenTelemetry span export`.
- Keep PRs focused and small; fill in the PR template checklist.
- Every migration must be committed (`makemigrations --check` must be clean).
- Update docs (`README.md`, `docs/`) when behavior or setup changes.

## Project layout

See `docs/ARCHITECTURE.md` for the repository structure and component roles, and
`docs/ROADMAP.md` for the feature roadmap and status.

## Reporting bugs / requesting features

Open an issue using the templates under `.github/ISSUE_TEMPLATE/`. For security
issues, follow `SECURITY.md` instead of opening a public issue.
