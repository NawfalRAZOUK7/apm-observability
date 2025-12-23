from __future__ import annotations

import time
from contextvars import ContextVar, Token

from django.conf import settings
from django.core.cache import cache

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_REQUEST_METHOD: ContextVar[str | None] = ContextVar("apm_request_method", default=None)


def set_request_method(method: str) -> Token:
    return _REQUEST_METHOD.set(method.upper() if method else "")

def reset_request_method(token: Token) -> None:
    _REQUEST_METHOD.reset(token)


def is_safe_method() -> bool:
    method = _REQUEST_METHOD.get()
    if not method:
        return False
    return method in SAFE_METHODS


def _ttl_seconds() -> int:
    try:
        return int(getattr(settings, "READ_AFTER_WRITE_TTL", 2))
    except (TypeError, ValueError):
        return 2


def mark_write() -> None:
    ttl = _ttl_seconds()
    if ttl <= 0:
        return
    cache.set("apm_last_write_ts", time.time(), timeout=ttl)


def should_force_primary() -> bool:
    ttl = _ttl_seconds()
    if ttl <= 0:
        return False
    last_write = cache.get("apm_last_write_ts")
    if not last_write:
        return False
    return (time.time() - float(last_write)) < ttl
