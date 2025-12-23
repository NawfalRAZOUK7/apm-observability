# Gemini Embeddings (APM Observability)

This guide documents the Gemini embedding pipeline for error similarity search.

## Requirements

- PostgreSQL + pgvector extension.
- `GEMINI_API_KEY` configured in your environment (never commit keys).

## Environment

Add these to your local `.env` or cluster `.env`:

```
GEMINI_API_KEY=your_key_here
GEMINI_EMBED_MODEL=text-embedding-004
GEMINI_EMBED_TIMEOUT=10
GEMINI_EMBED_MAX_CHARS=8000
GEMINI_EMBED_MIN_DELAY_S=0
```

## Create embeddings (errors-only)

If the database already existed before this feature, enable pgvector once:

```
psql -U apm -d apm -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Run inside the app container (or locally with Django env configured):

```
python manage.py embed_apirequests --status-from 500 --limit 1000 --batch-size 16
```

Options:
- `--since` ISO datetime (UTC) to embed only recent rows.
- `--include-tags` to include non-sensitive tag key/value pairs.
- `--force` to re-embed even if an embedding already exists.

## Semantic search API

Query for similar errors:

```
GET /api/requests/semantic-search/?q=timeout&limit=10
```

Optional filters:
- `service`
- `endpoint`
- `status_from` (default 500)

## Notes

- The first version embeds **errors only** (status >= 500) for high-signal search.
- If you move to a new embedding model, re-run embeddings with `--force`.
