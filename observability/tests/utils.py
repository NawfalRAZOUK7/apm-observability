# observability/tests/utils.py
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlencode

from django.utils import timezone

DEFAULT_INGEST_URL = "/api/requests/ingest/"


def make_event(**overrides: Any) -> dict[str, Any]:
    """
    Build a valid ingestion event (one item).
    You can override any field via kwargs.
    """
    base: dict[str, Any] = {
        "time": timezone.now().isoformat(),
        "service": "billing",
        "endpoint": "/api/v1/invoices",
        "method": "GET",
        "status_code": 200,
        "latency_ms": 123,
        "trace_id": "trace-001",
        "user_ref": "user-001",
        "tags": {"env": "test"},
    }
    base.update(overrides)
    return base


def make_events(
    n: int, *, trace_id_prefix: str = "t", start_index: int = 1, **overrides: Any
) -> list[dict[str, Any]]:
    """
    Build N valid events with unique trace_id values.
    """
    events: list[dict[str, Any]] = []
    for i in range(start_index, start_index + n):
        events.append(make_event(trace_id=f"{trace_id_prefix}{i}", **overrides))
    return events


def post_ingest(
    client: Any,
    events: Any,
    strict: bool = False,
    ingest_url: str = DEFAULT_INGEST_URL,
    **query: Any,
):
    """
    Post to the ingest endpoint.

    - events can be:
        * a list of events (most common)
        * a dict payload (e.g. {"events": [...]}) if you want the wrapper shape
    - strict=True adds ?strict=true
    - extra query params can be passed: max_events=2, max_errors=2, etc.
    """
    params: dict[str, Any] = dict(query)
    if strict:
        params["strict"] = "true"

    url = ingest_url
    if params:
        url = f"{ingest_url}?{urlencode(params, doseq=True)}"

    payload = events
    # Accept wrapper dict payload as-is
    if isinstance(events, Mapping):
        payload = dict(events)

    # Accept sequences (lists/tuples) of events
    if (
        isinstance(events, Sequence)
        and not isinstance(events, (str, bytes, bytearray))
        and not isinstance(events, Mapping)
    ):
        payload = list(events)

    return client.post(url, data=payload, format="json")
