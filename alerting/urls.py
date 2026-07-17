# alerting/urls.py
from rest_framework.routers import DefaultRouter

from .views import AlertRuleViewSet


class OptionalSlashRouter(DefaultRouter):
    trailing_slash = "/?"


router = OptionalSlashRouter()
router.register(r"rules", AlertRuleViewSet, basename="alertrule")

app_name = "alerting"
urlpatterns = router.urls
