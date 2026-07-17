# observability/otlp/ratelimit.py
"""Per-project ingest rate limiting via a token bucket (Phase 11).

In-process token bucket keyed by project. Suitable for single-process dev and
per-worker limiting; for cluster-wide limits back this with Redis in production.

    OTLP_RATE_LIMIT_PER_SEC   sustained points/sec per project (0 = unlimited)
    OTLP_RATE_LIMIT_BURST     bucket capacity (default = 2x rate, min 1)
"""

from __future__ import annotations

import os
import threading
import time


class TokenBucket:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.updated = time.monotonic()
        self._lock = threading.Lock()

    def allow(self, cost: float = 1.0, *, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        with self._lock:
            elapsed = max(0.0, now - self.updated)
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.updated = now
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False


_buckets: dict[int, TokenBucket] = {}
_registry_lock = threading.Lock()


def _config() -> tuple[float, float]:
    try:
        rate = float(os.environ.get("OTLP_RATE_LIMIT_PER_SEC", "0"))
    except ValueError:
        rate = 0.0
    try:
        burst = float(os.environ.get("OTLP_RATE_LIMIT_BURST", "0"))
    except ValueError:
        burst = 0.0
    if burst <= 0:
        burst = max(rate * 2, 1.0)
    return rate, burst


def allow(project_id, cost: float = 1.0, *, now: float | None = None) -> bool:
    """Return True if ``cost`` units are permitted for the project right now."""
    rate, burst = _config()
    if rate <= 0 or project_id is None:
        return True  # unlimited / no tenant
    with _registry_lock:
        bucket = _buckets.get(project_id)
        if bucket is None or bucket.rate != rate or bucket.capacity != burst:
            bucket = TokenBucket(rate, burst)
            _buckets[project_id] = bucket
    return bucket.allow(cost, now=now)


def reset() -> None:
    """Clear all buckets (used by tests)."""
    with _registry_lock:
        _buckets.clear()
