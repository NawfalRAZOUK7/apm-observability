# observability/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApiRequestViewSet

router = DefaultRouter()
router.register(r"requests", ApiRequestViewSet, basename="apirequest")

urlpatterns = [
    path("", include(router.urls)),
]
