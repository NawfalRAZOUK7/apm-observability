# observability/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApiRequestViewSet, HealthView  # add HealthView


class OptionalSlashRouter(DefaultRouter):
    trailing_slash = "/?"


router = OptionalSlashRouter()
router.register(r"requests", ApiRequestViewSet, basename="apirequest")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("", include(router.urls)),
]
