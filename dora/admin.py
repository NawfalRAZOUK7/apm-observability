# dora/admin.py
from django.contrib import admin

from .models import Deployment


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ("deployed_at", "environment", "version", "status", "caused_incident", "service")
    list_filter = ("environment", "status", "caused_incident")
    search_fields = ("version", "commit_sha", "service")
    date_hierarchy = "deployed_at"
