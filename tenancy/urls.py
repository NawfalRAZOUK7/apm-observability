# tenancy/urls.py
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import (
    ApiKeyListCreateView,
    ApiKeyRevokeView,
    ApiKeyRotateView,
    ProjectListView,
    ProjectUsageView,
)

app_name = "tenancy"

urlpatterns = [
    # JWT auth for the dashboard/API (human users).
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Tenant management.
    path("projects/", ProjectListView.as_view(), name="project_list"),
    path(
        "projects/<int:project_id>/keys/", ApiKeyListCreateView.as_view(), name="apikey_list_create"
    ),
    path(
        "projects/<int:project_id>/keys/<int:key_id>/rotate/",
        ApiKeyRotateView.as_view(),
        name="apikey_rotate",
    ),
    path(
        "projects/<int:project_id>/keys/<int:key_id>/revoke/",
        ApiKeyRevokeView.as_view(),
        name="apikey_revoke",
    ),
    path("projects/<int:project_id>/usage/", ProjectUsageView.as_view(), name="project_usage"),
]
