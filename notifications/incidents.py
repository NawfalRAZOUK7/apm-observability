# notifications/incidents.py
"""Incident lifecycle: open/update from alerts, acknowledge, assign, resolve,
compute MTTA/MTTR, build Grafana links, and generate postmortems (Phase 9)."""

from __future__ import annotations

import os
from urllib.parse import urlencode

from django.utils import timezone

from .models import Incident, IncidentEvent, Notification


def _dedup_key(notification: Notification) -> str:
    return notification.fingerprint or f"{notification.alertname}:{notification.severity}"


def _grafana_url(notification: Notification) -> str:
    base = os.environ.get("GRAFANA_BASE_URL", "").strip()
    if not base:
        return ""
    # Link to the dashboard windowed around the alert start (or now).
    start = notification.starts_at or timezone.now()
    frm = int((start.timestamp() - 600) * 1000)
    to = int((timezone.now().timestamp() + 60) * 1000)
    params = {"from": frm, "to": to}
    trace_id = (notification.labels or {}).get("trace_id", "")
    if trace_id:
        params["var-trace_id"] = trace_id
    return f"{base.rstrip('/')}/?{urlencode(params)}"


def open_or_update_from_notification(notification: Notification) -> Incident | None:
    """Open a new incident or update the existing open one for this alert.

    Firing alerts open/refresh an incident (deduped while open). Resolved alerts
    resolve the matching open incident. Info-severity alerts do not open
    incidents (dashboard-only).
    """
    if notification.severity == Notification.Severity.INFO:
        return None

    key = _dedup_key(notification)
    trace_id = (notification.labels or {}).get("trace_id", "") or ""

    if notification.status == Notification.Status.RESOLVED:
        incident = (
            Incident.objects.filter(dedup_key=key)
            .exclude(status=Incident.Status.RESOLVED)
            .order_by("-opened_at")
            .first()
        )
        if incident is None:
            return None
        resolve_incident(incident, message=f"Auto-resolved by alert {notification.alertname}.")
        return incident

    incident = (
        Incident.objects.filter(dedup_key=key)
        .exclude(status=Incident.Status.RESOLVED)
        .order_by("-opened_at")
        .first()
    )
    if incident is None:
        incident = Incident.objects.create(
            dedup_key=key,
            title=notification.summary or notification.alertname or "Incident",
            severity=notification.severity,
            description=notification.description,
            runbook_url=notification.runbook_url,
            trace_id=trace_id,
        )
        incident.grafana_url = _grafana_url(notification)
        incident.save(update_fields=["grafana_url"])
        IncidentEvent.objects.create(
            incident=incident,
            kind=IncidentEvent.Kind.OPENED,
            message=f"Opened from {notification.alertname} ({notification.severity}).",
        )
    else:
        IncidentEvent.objects.create(
            incident=incident,
            kind=IncidentEvent.Kind.NOTIFICATION,
            message=f"Alert re-fired: {notification.alertname}.",
        )
    return incident


def acknowledge_incident(incident: Incident, *, user=None, message: str = "") -> Incident:
    if incident.acknowledged_at is None:
        incident.acknowledged_at = timezone.now()
        if incident.status == Incident.Status.OPEN:
            incident.status = Incident.Status.ACKNOWLEDGED
        incident.acknowledged_by = user
        incident.save(update_fields=["acknowledged_at", "status", "acknowledged_by"])
        IncidentEvent.objects.create(
            incident=incident,
            kind=IncidentEvent.Kind.ACKNOWLEDGED,
            message=message or "Acknowledged.",
            actor=user,
        )
    return incident


def assign_incident(incident: Incident, *, owner, actor=None) -> Incident:
    incident.owner = owner
    incident.save(update_fields=["owner"])
    IncidentEvent.objects.create(
        incident=incident,
        kind=IncidentEvent.Kind.ASSIGNED,
        message=f"Assigned to {owner}.",
        actor=actor,
    )
    return incident


def resolve_incident(incident: Incident, *, user=None, message: str = "") -> Incident:
    if incident.status != Incident.Status.RESOLVED:
        incident.resolved_at = timezone.now()
        incident.status = Incident.Status.RESOLVED
        incident.save(update_fields=["resolved_at", "status"])
        IncidentEvent.objects.create(
            incident=incident,
            kind=IncidentEvent.Kind.RESOLVED,
            message=message or "Resolved.",
            actor=user,
        )
    return incident


def incident_metrics(queryset=None) -> dict:
    """Aggregate MTTA / MTTR (seconds) and counts over resolved incidents."""
    qs = queryset if queryset is not None else Incident.objects.all()
    resolved = qs.filter(status=Incident.Status.RESOLVED)
    mtta_values = [i.mtta_seconds for i in resolved if i.mtta_seconds is not None]
    mttr_values = [i.mttr_seconds for i in resolved if i.mttr_seconds is not None]
    return {
        "open": qs.exclude(status=Incident.Status.RESOLVED).count(),
        "resolved": resolved.count(),
        "mtta_seconds_avg": round(sum(mtta_values) / len(mtta_values), 1) if mtta_values else None,
        "mttr_seconds_avg": round(sum(mttr_values) / len(mttr_values), 1) if mttr_values else None,
    }


def generate_postmortem(incident: Incident) -> str:
    """Render a blameless postmortem markdown skeleton from the timeline."""
    lines = [
        f"# Postmortem — {incident.title}",
        "",
        f"- **Incident:** #{incident.pk}",
        f"- **Severity:** {incident.severity}",
        f"- **Status:** {incident.status}",
        f"- **Opened:** {incident.opened_at:%Y-%m-%d %H:%M:%S UTC}",
    ]
    if incident.acknowledged_at:
        lines.append(f"- **Acknowledged:** {incident.acknowledged_at:%Y-%m-%d %H:%M:%S UTC}")
    if incident.resolved_at:
        lines.append(f"- **Resolved:** {incident.resolved_at:%Y-%m-%d %H:%M:%S UTC}")
    if incident.mtta_seconds is not None:
        lines.append(f"- **MTTA:** {incident.mtta_seconds:.0f}s")
    if incident.mttr_seconds is not None:
        lines.append(f"- **MTTR:** {incident.mttr_seconds:.0f}s")
    if incident.runbook_url:
        lines.append(f"- **Runbook:** {incident.runbook_url}")
    if incident.grafana_url:
        lines.append(f"- **Dashboard snapshot:** {incident.grafana_url}")
    if incident.trace_id:
        lines.append(f"- **Trace:** `{incident.trace_id}`")

    lines += ["", "## Summary", "", incident.description or "_TODO: what happened._", ""]
    lines += ["## Timeline", ""]
    for event in incident.events.all():
        actor = f" ({event.actor})" if event.actor_id else ""
        lines.append(f"- `{event.at:%H:%M:%S}` **{event.kind}**{actor}: {event.message}")
    lines += [
        "",
        "## Root cause",
        "",
        "_TODO._",
        "",
        "## What went well / what didn't",
        "",
        "_TODO._",
        "",
        "## Action items",
        "",
        "- [ ] _TODO_",
        "",
    ]
    return "\n".join(lines)


def _timeline_text(incident: Incident) -> str:
    rows = [f"- {e.at:%Y-%m-%d %H:%M:%S} [{e.kind}] {e.message}" for e in incident.events.all()]
    return "\n".join(rows)


def generate_ai_postmortem(incident: Incident) -> str:
    """LLM-drafted postmortem from the incident timeline.

    Falls back to the deterministic template (generate_postmortem) whenever no
    LLM is configured or the call fails, so this always returns useful markdown
    at $0.
    """
    from observability.ai import llm

    template = generate_postmortem(incident)
    if not llm.is_available():
        return template

    system = (
        "You are an SRE writing a concise, blameless postmortem. Use the incident "
        "metadata and timeline to fill in Summary, Root cause (best hypothesis, "
        "clearly marked as such), Impact, and 3-5 concrete Action items. Output "
        "GitHub-flavored Markdown. Do not invent facts not supported by the timeline."
    )
    prompt = (
        f"Incident: {incident.title}\n"
        f"Severity: {incident.severity}\n"
        f"Status: {incident.status}\n"
        f"MTTA: {incident.mtta_seconds}s  MTTR: {incident.mttr_seconds}s\n"
        f"Runbook: {incident.runbook_url or 'n/a'}\n\n"
        f"Timeline:\n{_timeline_text(incident)}\n\n"
        f"Here is a template to follow and improve:\n\n{template}"
    )
    try:
        drafted = llm.complete(prompt, system=system)
    except llm.LLMError:
        return template
    return drafted.strip() or template
