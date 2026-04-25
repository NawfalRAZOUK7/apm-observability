from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Iterable
from datetime import UTC

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from observability.ai.gemini import GeminiEmbedError, embed_texts
from observability.models import ApiRequest, ApiRequestEmbedding

SENSITIVE_TAG_HINTS = (
    "user",
    "email",
    "token",
    "auth",
    "password",
    "session",
    "secret",
    "key",
)


def _safe_tags(tags: object, *, include_tags: bool) -> list[str]:
    if not include_tags:
        return []
    if not isinstance(tags, dict):
        return []

    safe_pairs: list[str] = []
    for key, value in tags.items():
        key_str = str(key)
        lower = key_str.lower()
        if any(hint in lower for hint in SENSITIVE_TAG_HINTS):
            continue
        safe_pairs.append(f"{key_str}={value}")
    return safe_pairs


def _build_embedding_text(req: ApiRequest, *, include_tags: bool) -> str:
    parts = [
        f"service={req.service}",
        f"endpoint={req.endpoint}",
        f"method={req.method}",
        f"status={req.status_code}",
        f"latency_ms={req.latency_ms}",
    ]
    safe_pairs = _safe_tags(req.tags, include_tags=include_tags)
    if safe_pairs:
        parts.append("tags=" + ",".join(safe_pairs))
    return " ".join(parts)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "Create Gemini embeddings for ApiRequest rows (errors-only by default)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--status-from",
            type=int,
            default=500,
            help="Only embed rows with status_code >= this value (default: 500).",
        )
        parser.add_argument(
            "--since",
            default=None,
            help="Only embed rows with time >= this ISO datetime (UTC).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of rows to embed in this run (default: 1000).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=16,
            help="Batch size for embedding API calls (default: 16).",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.0,
            help="Optional sleep between batches (seconds).",
        )
        parser.add_argument(
            "--include-tags",
            action="store_true",
            help="Include non-sensitive tag key/value pairs in embedding text.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-embed even if an embedding already exists.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be embedded, without calling the API.",
        )

    def handle(self, *args, **options):
        status_from = int(options["status_from"])
        limit = int(options["limit"])
        batch_size = int(options["batch_size"])
        include_tags = bool(options["include_tags"])
        force = bool(options["force"])
        dry_run = bool(options["dry_run"])
        sleep_s = float(options["sleep"])

        if batch_size <= 0:
            raise CommandError("--batch-size must be > 0.")
        if limit <= 0:
            raise CommandError("--limit must be > 0.")

        since_raw = options.get("since")
        since_dt = None
        if since_raw:
            since_dt = parse_datetime(since_raw)
            if since_dt is None:
                raise CommandError("--since must be an ISO datetime (e.g. 2025-01-01T00:00:00Z).")
            if timezone.is_naive(since_dt):
                since_dt = timezone.make_aware(since_dt, timezone=UTC)

        qs = ApiRequest.objects.filter(status_code__gte=status_from)
        if since_dt is not None:
            qs = qs.filter(time__gte=since_dt)
        if not force:
            qs = qs.filter(embedding__isnull=True)

        qs = qs.order_by("id")[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No rows to embed."))
            return

        model_name = os.environ.get("GEMINI_EMBED_MODEL", "text-embedding-004").strip()
        if not model_name:
            model_name = "text-embedding-004"

        self.stdout.write(
            f"Embedding {total} rows (status >= {status_from}, "
            f"batch={batch_size}, model={model_name})."
        )

        buffered: list[ApiRequest] = []
        created = 0
        processed = 0

        def flush(batch: Iterable[ApiRequest]) -> None:
            nonlocal created, processed

            reqs = list(batch)
            if not reqs:
                return

            texts = [_build_embedding_text(req, include_tags=include_tags) for req in reqs]
            hashes = [_content_hash(text) for text in texts]

            processed += len(reqs)

            if dry_run:
                created += len(reqs)
                return

            try:
                vectors = embed_texts(texts)
            except GeminiEmbedError as exc:
                raise CommandError(f"Embedding failed: {exc}") from exc

            embeddings = []
            for req, vector, content_hash in zip(reqs, vectors, hashes, strict=True):
                embeddings.append(
                    ApiRequestEmbedding(
                        request=req,
                        source=ApiRequestEmbedding.Source.ERROR,
                        model=model_name,
                        content_hash=content_hash,
                        embedding=vector,
                    )
                )

            ApiRequestEmbedding.objects.bulk_create(embeddings, ignore_conflicts=True)
            created += len(embeddings)

        for req in qs.iterator(chunk_size=batch_size):
            buffered.append(req)
            if len(buffered) >= batch_size:
                flush(buffered)
                buffered = []
                if sleep_s:
                    time.sleep(sleep_s)

        if buffered:
            flush(buffered)

        self.stdout.write(self.style.SUCCESS(f"Embedded {created} rows (processed {processed})."))
