# observability/otlp/sampling.py
"""Tail-based sampling for trace ingestion (Phase 11).

Runs after spans are parsed (so the whole trace is visible): always keep traces
that contain an error or a slow span, and keep the rest at a configurable rate.
The probabilistic decision is deterministic per trace_id (hash-based) so every
span of a trace shares the same keep/drop verdict.

    OTLP_TAIL_SAMPLE_RATE   fraction of non-interesting traces to keep (default 1.0)
    OTLP_SLOW_MS            span duration considered "slow" (default 500)
"""

from __future__ import annotations

import hashlib
import os


def _rate() -> float:
    try:
        return max(0.0, min(1.0, float(os.environ.get("OTLP_TAIL_SAMPLE_RATE", "1.0"))))
    except ValueError:
        return 1.0


def _slow_ms() -> int:
    try:
        return int(os.environ.get("OTLP_SLOW_MS", "500"))
    except ValueError:
        return 500


def _keep_by_hash(trace_id: str, rate: float) -> bool:
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    digest = hashlib.sha256(trace_id.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return bucket < rate


def tail_sample(span_dicts: list[dict]) -> tuple[list[dict], int]:
    """Return (kept_spans, dropped_count) applying the tail policy per trace."""
    rate, slow = _rate(), _slow_ms()
    if rate >= 1.0:
        return span_dicts, 0

    by_trace: dict[str, list[dict]] = {}
    for s in span_dicts:
        by_trace.setdefault(s.get("trace_id", ""), []).append(s)

    kept: list[dict] = []
    dropped = 0
    for trace_id, spans in by_trace.items():
        interesting = any(
            s.get("status_code") == "error" or (s.get("duration_ms") or 0) >= slow for s in spans
        )
        if interesting or _keep_by_hash(trace_id, rate):
            kept.extend(spans)
        else:
            dropped += len(spans)
    return kept, dropped
