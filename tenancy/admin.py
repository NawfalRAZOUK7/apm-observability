# tenancy/admin.py
from django.contrib import admin

from .models import ApiKey, Environment, Membership, Organization, Project, UsageRecord


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


class EnvironmentInline(admin.TabularInline):
    model = Environment
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    inlines = [MembershipInline]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("slug", "organization", "monthly_event_quota", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "slug")
    inlines = [EnvironmentInline]


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("prefix", "project", "environment", "can_write", "is_active", "created_at", "last_used_at")
    list_filter = ("can_write", "project")
    search_fields = ("prefix", "name")
    readonly_fields = ("prefix", "hashed_key", "created_at", "last_used_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "created_at")
    list_filter = ("role", "organization")


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ("project", "period", "event_count")
    list_filter = ("project",)
