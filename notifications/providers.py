# notifications/providers.py
"""Pluggable notification channel providers (the free-first provider pattern).

Every channel has a real driver and a free/local driver, selected by env var.
Defaults are free: chat -> console, pager -> console. Flip the env var to hit a
real Slack/Discord webhook or a self-hosted ntfy instance -- no code change.

    CHAT_PROVIDER   = console | slack | discord | none      (default: console)
    PAGER_PROVIDER  = console | ntfy | none                 (default: console)
    SLACK_WEBHOOK_URL / DISCORD_WEBHOOK_URL / NTFY_URL / NTFY_TOPIC

Delivery uses only the standard library (urllib) so it adds no dependency.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger("notifications")

# Severity -> channels policy. Mirrors the Alertmanager routing tree so the
# app remains the source of truth even if the routing config drifts.
#   Critical -> pager + chat, Warning -> chat, Info -> dashboard only.
SEVERITY_POLICY: dict[str, list[str]] = {
    "critical": ["pager", "chat"],
    "warning": ["chat"],
    "info": [],
    "unknown": ["chat"],
}

_TIMEOUT = float(os.environ.get("NOTIFY_HTTP_TIMEOUT", "5"))


def _post_json(url: str, payload: dict, headers: dict | None = None) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (trusted internal URLs)
        resp.read()


class BaseProvider:
    name = "base"

    def send(self, notification) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class NullProvider(BaseProvider):
    """Dashboard-only: the notification is stored but not pushed anywhere."""

    name = "none"

    def send(self, notification) -> None:
        return None


class ConsoleProvider(BaseProvider):
    """Free default: log the notification. Proves the path with zero config."""

    name = "console"

    def send(self, notification) -> None:
        logger.warning(
            "notify.console",
            extra={
                "severity": notification.severity,
                "alertname": notification.alertname,
                "status": notification.status,
                "summary": notification.summary,
            },
        )


class SlackProvider(BaseProvider):
    name = "slack"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, notification) -> None:
        emoji = {"critical": ":rotating_light:", "warning": ":warning:"}.get(
            notification.severity, ":information_source:"
        )
        text = (
            f"{emoji} *[{notification.severity.upper()}] {notification.alertname}* "
            f"({notification.status})\n{notification.summary}"
        )
        if notification.runbook_url:
            text += f"\nRunbook: {notification.runbook_url}"
        _post_json(self.webhook_url, {"text": text})


class DiscordProvider(BaseProvider):
    name = "discord"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, notification) -> None:
        content = (
            f"**[{notification.severity.upper()}] {notification.alertname}** "
            f"({notification.status})\n{notification.summary}"
        )
        if notification.runbook_url:
            content += f"\nRunbook: <{notification.runbook_url}>"
        _post_json(self.webhook_url, {"content": content})


class NtfyProvider(BaseProvider):
    """Self-hosted ntfy.sh -- free replacement for PagerDuty phone push."""

    name = "ntfy"

    def __init__(self, base_url: str, topic: str):
        self.base_url = base_url.rstrip("/")
        self.topic = topic

    def send(self, notification) -> None:
        priority = {"critical": "urgent", "warning": "high"}.get(
            notification.severity, "default"
        )
        url = f"{self.base_url}/{self.topic}"
        body = f"{notification.summary or notification.alertname}".encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Title", f"[{notification.severity.upper()}] {notification.alertname}")
        req.add_header("Priority", priority)
        if notification.runbook_url:
            req.add_header("Actions", f"view, Runbook, {notification.runbook_url}")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            resp.read()


def get_chat_provider() -> BaseProvider:
    choice = os.environ.get("CHAT_PROVIDER", "console").strip().lower()
    if choice == "slack":
        url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
        return SlackProvider(url) if url else ConsoleProvider()
    if choice == "discord":
        url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        return DiscordProvider(url) if url else ConsoleProvider()
    if choice == "none":
        return NullProvider()
    return ConsoleProvider()


def get_pager_provider() -> BaseProvider:
    choice = os.environ.get("PAGER_PROVIDER", "console").strip().lower()
    if choice == "ntfy":
        url = os.environ.get("NTFY_URL", "").strip()
        topic = os.environ.get("NTFY_TOPIC", "apm-alerts").strip()
        return NtfyProvider(url, topic) if url else ConsoleProvider()
    if choice == "none":
        return NullProvider()
    return ConsoleProvider()


def dispatch(notification) -> None:
    """Fan a stored notification out to its severity-mapped channels.

    Records the outcome on the notification (delivered / delivery_error). The
    sink itself already persisted the row, so 'dashboard only' (info) is always
    satisfied even when no external channel fires.
    """
    channels = SEVERITY_POLICY.get(notification.severity, ["chat"])
    notification.channels = channels

    if not channels:
        notification.delivered = True
        notification.delivery_error = ""
        return

    providers = {"chat": get_chat_provider(), "pager": get_pager_provider()}
    errors: list[str] = []
    for channel in channels:
        provider = providers.get(channel)
        if provider is None:
            continue
        try:
            provider.send(notification)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            errors.append(f"{channel}:{provider.name}: {exc}")
            logger.warning("notify.delivery_failed", extra={"channel": channel, "error": str(exc)})

    notification.delivered = not errors
    notification.delivery_error = "; ".join(errors)
