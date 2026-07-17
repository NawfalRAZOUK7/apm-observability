"""Backfill existing ApiRequest rows to a default tenant (Phase 5).

Existing data predates multi-tenancy, so it is assigned to a single
``default/default`` organization/project. New ingestion resolves the project
from the API key (Phase 6). Reversible: the backfill only sets rows it created
the default for; reverse nulls them back.
"""

from django.db import migrations

DEFAULT_ORG_SLUG = "default"
DEFAULT_PROJECT_SLUG = "default"


def backfill(apps, schema_editor):
    Organization = apps.get_model("tenancy", "Organization")
    Project = apps.get_model("tenancy", "Project")
    Environment = apps.get_model("tenancy", "Environment")
    ApiRequest = apps.get_model("observability", "ApiRequest")

    org, _ = Organization.objects.get_or_create(slug=DEFAULT_ORG_SLUG, defaults={"name": "Default"})
    project, _ = Project.objects.get_or_create(
        organization=org, slug=DEFAULT_PROJECT_SLUG, defaults={"name": "Default"}
    )
    Environment.objects.get_or_create(project=project, kind="production")

    ApiRequest.objects.filter(project__isnull=True).update(project=project)


def reverse(apps, schema_editor):
    Project = apps.get_model("tenancy", "Project")
    ApiRequest = apps.get_model("observability", "ApiRequest")
    project = Project.objects.filter(slug=DEFAULT_PROJECT_SLUG).first()
    if project is not None:
        ApiRequest.objects.filter(project=project).update(project=None)


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0010_apirequest_project"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse),
    ]
