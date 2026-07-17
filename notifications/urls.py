# notifications/urls.py
from django.urls import path

from .incident_views import (
    IncidentAckView,
    IncidentAssignView,
    IncidentDetailView,
    IncidentListView,
    IncidentMetricsView,
    IncidentPostmortemView,
    IncidentResolveView,
)
from .views import AlertmanagerWebhookView, NotificationListView

app_name = "notifications"

urlpatterns = [
    # Alertmanager posts here (see docker/monitoring/alertmanager/alertmanager.yml).
    path("notify", AlertmanagerWebhookView.as_view(), name="notify"),
    path("notify/", AlertmanagerWebhookView.as_view()),
    # Incident management (Phase 9).
    path("incidents/", IncidentListView.as_view(), name="incident_list"),
    path("incidents/metrics/", IncidentMetricsView.as_view(), name="incident_metrics"),
    path("incidents/<int:pk>/", IncidentDetailView.as_view(), name="incident_detail"),
    path("incidents/<int:pk>/ack/", IncidentAckView.as_view(), name="incident_ack"),
    path("incidents/<int:pk>/assign/", IncidentAssignView.as_view(), name="incident_assign"),
    path("incidents/<int:pk>/resolve/", IncidentResolveView.as_view(), name="incident_resolve"),
    path(
        "incidents/<int:pk>/postmortem/",
        IncidentPostmortemView.as_view(),
        name="incident_postmortem",
    ),
    # Dashboard-only channel + audit trail.
    path("", NotificationListView.as_view(), name="list"),
]
