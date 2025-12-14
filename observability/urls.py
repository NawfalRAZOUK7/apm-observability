# observability/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApiRequestViewSet

class OptionalSlashRouter(DefaultRouter):
    trailing_slash = "/?"


router = OptionalSlashRouter()
router.register(r"requests", ApiRequestViewSet, basename="apirequest")

urlpatterns = [
    path("", include(router.urls)),
]