# dora/urls.py
from django.urls import path

from .views import DeploymentListCreateView, DoraMetricsView

app_name = "dora"

urlpatterns = [
    path("deployments/", DeploymentListCreateView.as_view(), name="deployments"),
    path("metrics/", DoraMetricsView.as_view(), name="metrics"),
]
