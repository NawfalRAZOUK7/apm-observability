# observability/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .analytics_views import AnomalyView, IssueListView, NLQueryView, ServiceMapView
from .traces_views import TraceDetailView, TraceListView
from .views import ApiRequestViewSet, HealthView  # add HealthView


class OptionalSlashRouter(DefaultRouter):
    trailing_slash = "/?"


router = OptionalSlashRouter()
router.register(r"requests", ApiRequestViewSet, basename="apirequest")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    # Service dependency map derived from span edges (Phase 7).
    path("service-map/", ServiceMapView.as_view(), name="service-map"),
    # Statistical anomaly detection over API request series (Phase 8).
    path("anomalies/", AnomalyView.as_view(), name="anomalies"),
    # Trace list + waterfall detail (Phase 12).
    path("traces/", TraceListView.as_view(), name="trace-list"),
    path("traces/<str:trace_id>/", TraceDetailView.as_view(), name="trace-detail"),
    # LLM intelligence (Phase 13): grouped errors + natural-language queries.
    path("issues/", IssueListView.as_view(), name="issues"),
    path("nl-query/", NLQueryView.as_view(), name="nl-query"),
    path("", include(router.urls)),
]
