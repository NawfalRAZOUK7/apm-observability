# observability/management/commands/group_errors.py
"""Recompute error Issues by fingerprinting recent error requests (Phase 13).

python manage.py group_errors --hours 24        # all projects
python manage.py group_errors --project demo
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from observability.analytics.issues import rebuild_issues
from tenancy.models import Project


class Command(BaseCommand):
    help = "Group recent error requests into Issues."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)
        parser.add_argument("--project", default=None, help="Project slug (default: all).")

    def handle(self, *args, **opts):
        since = timezone.now() - timedelta(hours=opts["hours"])
        projects = (
            [Project.objects.get(slug=opts["project"])]
            if opts["project"]
            else list(Project.objects.all()) or [None]
        )
        total = 0
        for project in projects:
            n = rebuild_issues(project=project, since=since)
            total += n
            label = project.slug if project else "(all)"
            self.stdout.write(f"  {label}: {n} issue(s)")
        self.stdout.write(self.style.SUCCESS(f"Grouped into {total} issue(s)."))
