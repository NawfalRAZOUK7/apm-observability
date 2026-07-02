from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from observability.models import ApiRequest


class Command(BaseCommand):
    help = (
        "Run data-quality checks on ApiRequest (nulls, ranges, duplicates, "
        "freshness). Exits non-zero when a hard check fails, so it can gate CI."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-minutes",
            type=int,
            default=0,
            help="Fail if the newest event is older than this many minutes (0 = skip).",
        )
        parser.add_argument(
            "--fail-on-empty",
            action="store_true",
            help="Treat an empty table as a failure.",
        )
        parser.add_argument(
            "--max-dup-ratio",
            type=float,
            default=1.0,
            help="Fail if the duplicate trace_id ratio exceeds this (0-1). Default 1.0 = off.",
        )

    def handle(self, *args, **opts):
        total = ApiRequest.objects.count()
        failures: list[str] = []
        warnings: list[str] = []

        self.stdout.write(f"Rows: {total}")

        if total == 0:
            msg = "table is empty"
            (failures if opts["fail_on_empty"] else warnings).append(msg)
            self._report(failures, warnings)
            return

        # 1) Required fields must not be null/blank.
        missing = ApiRequest.objects.filter(
            Q(service__isnull=True)
            | Q(service__exact="")
            | Q(endpoint__isnull=True)
            | Q(endpoint__exact="")
            | Q(method__isnull=True)
            | Q(method__exact="")
        ).count()
        self.stdout.write(f"Missing required fields (service/endpoint/method): {missing}")
        if missing:
            failures.append(f"{missing} rows with missing service/endpoint/method")

        # 2) status_code must be a valid HTTP code.
        bad_status = ApiRequest.objects.filter(
            Q(status_code__lt=100) | Q(status_code__gt=599)
        ).count()
        self.stdout.write(f"Invalid status_code (<100 or >599): {bad_status}")
        if bad_status:
            failures.append(f"{bad_status} rows with invalid status_code")

        # 3) latency_ms must be non-negative.
        bad_latency = ApiRequest.objects.filter(latency_ms__lt=0).count()
        self.stdout.write(f"Negative latency_ms: {bad_latency}")
        if bad_latency:
            failures.append(f"{bad_latency} rows with negative latency_ms")

        # 4) Duplicate trace_id ratio (ignoring null/blank).
        with_trace = ApiRequest.objects.exclude(Q(trace_id__isnull=True) | Q(trace_id__exact=""))
        n_trace = with_trace.count()
        distinct_trace = with_trace.values("trace_id").distinct().count()
        dup = n_trace - distinct_trace
        ratio = (dup / n_trace) if n_trace else 0.0
        self.stdout.write(f"Duplicate trace_id: {dup}/{n_trace} (ratio={ratio:.3f})")
        if ratio > opts["max_dup_ratio"]:
            failures.append(f"duplicate trace_id ratio {ratio:.3f} exceeds {opts['max_dup_ratio']}")

        # 5) Freshness of the most recent event.
        if opts["max_age_minutes"] > 0:
            newest = ApiRequest.objects.order_by("-time").values_list("time", flat=True).first()
            if newest is None:
                failures.append("no timestamped rows for freshness check")
            else:
                age = timezone.now() - newest
                self.stdout.write(f"Newest event age: {age}")
                if age > timedelta(minutes=opts["max_age_minutes"]):
                    failures.append(
                        f"newest event is {age} old (> {opts['max_age_minutes']}m threshold)"
                    )

        self._report(failures, warnings)

    def _report(self, failures: list[str], warnings: list[str]) -> None:
        for w in warnings:
            self.stdout.write(self.style.WARNING(f"WARN: {w}"))
        if failures:
            for f in failures:
                self.stdout.write(self.style.ERROR(f"FAIL: {f}"))
            # Non-zero exit for CI gating.
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Data quality checks passed."))
