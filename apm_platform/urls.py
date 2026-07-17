"""
URL configuration for apm_platform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from pathlib import Path

from django.apps import apps
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path


def dashboard_view(_request):
    # Serve the single-file dashboard verbatim by reading it off disk. It's a
    # React app, not a Django template — its JSX {{ }} must never touch the
    # template engine, so we do NOT use get_template()/render().
    path_ = Path(apps.get_app_config("observability").path) / "templates" / "dashboard.html"
    return HttpResponse(path_.read_text(encoding="utf-8"))
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from observability.otlp.views import OTLPLogsView, OTLPMetricsView, OTLPTracesView

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("django_prometheus.urls")),
    path("api/", include("observability.urls")),
    # Multi-tenancy: JWT auth, projects, API keys, usage (Phase 5).
    path("api/tenancy/", include("tenancy.urls")),
    # Tenant-defined alert rules (Phase 10).
    path("api/alerting/", include("alerting.urls")),
    # DORA delivery metrics (Phase 18).
    path("api/dora/", include("dora.urls")),
    # Native OTLP/HTTP JSON trace ingestion (Phase 6). Stock OTel exporters set
    # OTEL_EXPORTER_OTLP_ENDPOINT to this host; the SDK appends /v1/traces.
    path("v1/traces", OTLPTracesView.as_view(), name="otlp_traces"),
    path("v1/traces/", OTLPTracesView.as_view()),
    path("v1/metrics", OTLPMetricsView.as_view(), name="otlp_metrics"),
    path("v1/metrics/", OTLPMetricsView.as_view()),
    path("v1/logs", OTLPLogsView.as_view(), name="otlp_logs"),
    path("v1/logs/", OTLPLogsView.as_view()),
    # Alert delivery: Alertmanager webhook sink + notifications dashboard (Phase 4).
    path("sink/", include("notifications.urls")),
    # First-party dashboard UI (Phase 12).
    path("dashboard/", dashboard_view, name="dashboard"),
    # OpenAPI schema + interactive docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
