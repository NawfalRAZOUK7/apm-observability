# observability/analytics/issues.py
"""Group similar errors into Issues via Sentry-style fingerprinting (Phase 13).

Pure-Python normalization + signatures, so it runs on SQLite and PostgreSQL and
needs no LLM/embeddings. (Embedding-based merging of near-duplicate signatures is
an optional enhancement layered on top when a provider is configured.)
"""
from __future__ import annotations

import re
from datetime import datetime

from django.db import transaction

from observability.models import ApiRequest, Issue

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_HEX = re.compile(r"\b[0-9a-f]{16,}\b", re.I)
_NUM = re.compile(r"\d+")


def normalize(text: str) -> str:
    """Collapse volatile tokens (ids, numbers) so like errors share a signature."""
    text = (text or "").strip().lower()
    text = _UUID.sub("<uuid>", text)
    text = _HEX.sub("<hex>", text)
    text = _NUM.sub("N", text)
    return re.sub(r"\s+", " ", text)


def _status_class(status_code: int | None) -> str:
    if not status_code:
        return "5xx"
    return f"{status_code // 100}xx"


def _message_of(row: ApiRequest) -> str:
    tags = row.tags or {}
    return tags.get("error") or tags.get("message") or f"HTTP {row.status_code} on {row.endpoint}"


def signature_for(row: ApiRequest) -> str:
    return (
        f"{row.service}|{row.method}|{row.endpoint}|"
        f"{_status_class(row.status_code)}|{normalize(_message_of(row))}"
    )


def group_error_rows(rows) -> dict[str, dict]:
    """Aggregate error ApiRequests into {signature: issue-dict}."""
    groups: dict[str, dict] = {}
    for row in rows:
        sig = signature_for(row)
        g = groups.get(sig)
        message = _message_of(row)
        if g is None:
            groups[sig] = {
                "signature": sig,
                "title": f"{row.method} {row.endpoint} · {_status_class(row.status_code)}",
                "service": row.service,
                "endpoint": row.endpoint,
                "method": row.method,
                "status_code": row.status_code,
                "count": 1,
                "first_seen": row.time,
                "last_seen": row.time,
                "sample_message": message,
            }
        else:
            g["count"] += 1
            g["first_seen"] = min(g["first_seen"], row.time)
            g["last_seen"] = max(g["last_seen"], row.time)
    return groups


@transaction.atomic
def rebuild_issues(*, project=None, since: datetime | None = None, until: datetime | None = None) -> int:
    """Recompute issues for a project from its error requests. Returns issue count."""
    qs = ApiRequest.objects.filter(status_code__gte=500)
    if project is not None:
        qs = qs.filter(project=project)
    if since is not None:
        qs = qs.filter(time__gte=since)
    if until is not None:
        qs = qs.filter(time__lt=until)

    groups = group_error_rows(qs.only("service", "method", "endpoint", "status_code", "time", "tags"))
    for sig, data in groups.items():
        Issue.objects.update_or_create(
            project=project,
            signature=sig,
            defaults={
                "title": data["title"],
                "service": data["service"],
                "endpoint": data["endpoint"],
                "method": data["method"],
                "status_code": data["status_code"],
                "count": data["count"],
                "first_seen": data["first_seen"],
                "last_seen": data["last_seen"],
                "sample_message": data["sample_message"],
            },
        )
    return len(groups)
