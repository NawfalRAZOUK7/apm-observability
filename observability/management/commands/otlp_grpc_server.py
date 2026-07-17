# observability/management/commands/otlp_grpc_server.py
"""Run the native OTLP/gRPC receiver on :4317 (Phase 11).

    python manage.py otlp_grpc_server --port 4317

Requires grpcio + opentelemetry-proto (in requirements.txt). Point a stock OTel
exporter's OTLP/gRPC endpoint at this host:4317.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Serve native OTLP over gRPC on the given port (default 4317)."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=4317)

    def handle(self, *args, **opts):
        try:
            from observability.otlp.grpc_server import serve
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise CommandError(
                "gRPC support needs grpcio + opentelemetry-proto: "
                "pip install grpcio opentelemetry-proto"
            ) from exc
        port = opts["port"]
        self.stdout.write(
            self.style.SUCCESS(f"OTLP/gRPC receiver listening on :{port} (Ctrl-C to stop)")
        )
        serve(port)
