# tenancy/management/commands/seed_tenant.py
"""Seed a demo tenant (org/project/environment) and mint an ingestion API key.

Idempotent for the org/project/environment; mints a fresh key each run. With
``--quiet`` it prints ONLY the plaintext key on stdout (for capture in scripts);
otherwise it prints a human-readable summary.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from tenancy.models import ApiKey, Environment, Organization, Project


class Command(BaseCommand):
    help = "Create a demo organization/project/environment and print a new API key."

    def add_arguments(self, parser):
        parser.add_argument("--org", default="demo", help="Organization slug (default: demo).")
        parser.add_argument("--project", default="demo", help="Project slug (default: demo).")
        parser.add_argument(
            "--env",
            default="production",
            choices=[c.value for c in Environment.Kind],
            help="Environment kind (default: production).",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Print only the plaintext key on stdout (for scripting).",
        )

    def handle(self, *args, **opts):
        org, _ = Organization.objects.get_or_create(
            slug=opts["org"], defaults={"name": opts["org"].title()}
        )
        project, _ = Project.objects.get_or_create(
            organization=org, slug=opts["project"], defaults={"name": opts["project"].title()}
        )
        environment, _ = Environment.objects.get_or_create(project=project, kind=opts["env"])

        api_key, plaintext = ApiKey.generate(
            project=project, environment=environment, name="demo-features"
        )

        if opts["quiet"]:
            # Only the key on stdout so callers can capture it cleanly.
            self.stdout.write(plaintext)
            return

        self.stdout.write(self.style.SUCCESS("Seeded demo tenant:"))
        self.stdout.write(f"  organization : {org.slug}")
        self.stdout.write(f"  project      : {project.slug} (id={project.id})")
        self.stdout.write(f"  environment  : {environment.kind}")
        self.stdout.write(f"  api key id   : {api_key.id} (prefix {api_key.prefix}…)")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Ingestion API key (shown once):"))
        self.stdout.write(f"  {plaintext}")
