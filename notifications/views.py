# notifications/views.py
from __future__ import annotations

from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .incidents import open_or_update_from_notification
from .models import Notification
from .providers import dispatch
from .serializers import NotificationSerializer


def _normalize_severity(value: str) -> str:
    value = (value or "").strip().lower()
    valid = {c.value for c in Notification.Severity}
    return value if value in valid else Notification.Severity.UNKNOWN


class AlertmanagerWebhookView(APIView):
    """Receive Alertmanager webhook payloads and record + dispatch them.

    This is the universal free mock: point every Alertmanager receiver's
    ``webhook_configs.url`` here. The endpoint is intentionally unauthenticated
    for the internal Docker network; put it behind an ingest key in production.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={201: None},
        description="Alertmanager webhook receiver. Stores each alert and fans "
        "it out to severity-mapped channels (pager/chat).",
    )
    def post(self, request):
        payload = request.data or {}
        alerts = payload.get("alerts") or []
        created: list[Notification] = []

        for alert in alerts:
            labels = alert.get("labels") or {}
            annotations = alert.get("annotations") or {}
            notification = Notification(
                fingerprint=alert.get("fingerprint", ""),
                status=alert.get("status", Notification.Status.FIRING),
                severity=_normalize_severity(labels.get("severity", "")),
                alertname=labels.get("alertname", ""),
                summary=annotations.get("summary", ""),
                description=annotations.get("description", ""),
                runbook_url=annotations.get("runbook_url", "")
                or annotations.get("runbook", ""),
                labels=labels,
                annotations=annotations,
                starts_at=parse_datetime(alert.get("startsAt", "") or "") or None,
                ends_at=parse_datetime(alert.get("endsAt", "") or "") or None,
                raw=alert,
            )
            # Dispatch only firing alerts to external channels; resolved alerts
            # are recorded for the timeline but do not re-page.
            if notification.status == Notification.Status.FIRING:
                dispatch(notification)
            else:
                notification.delivered = True
            notification.save()
            created.append(notification)

            # Turn the alert into (or resolve) a tracked incident (Phase 9).
            open_or_update_from_notification(notification)

        return Response(
            {"received": len(alerts), "stored": len(created)},
            status=status.HTTP_201_CREATED,
        )


class NotificationListView(ListAPIView):
    """Recent notifications (the dashboard-only channel + audit trail)."""

    serializer_class = NotificationSerializer
    permission_classes = [AllowAny]
    queryset = Notification.objects.all()
    filterset_fields = ["severity", "status", "alertname", "delivered"]
    ordering_fields = ["received_at", "severity"]
    ordering = ["-received_at"]
