from __future__ import annotations

import json
import os
import random
import ssl
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from faker import Faker

from observability.models import ApiRequest
from observability.serializers import ApiRequestIngestItemSerializer

DEFAULT_SERVICES = ["api", "web", "auth"]
DEFAULT_ENDPOINTS = ["/health", "/login", "/orders", "/home", "/search"]

SERVICE_ENDPOINTS = {
    "api": ["/health", "/orders", "/search"],
    "web": ["/home", "/search"],
    "auth": ["/login"],
}

ENDPOINT_METHODS = {
    "/health": ["GET"],
    "/login": ["POST"],
    "/orders": ["GET", "POST"],
    "/home": ["GET"],
    "/search": ["GET"],
}

FALLBACK_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


@dataclass(frozen=True)
class SeedWindow:
    start: datetime
    end: datetime


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or default


def _parse_dt_or_date(value: str, *, end_of_day: bool) -> datetime:
    value = (value or "").strip()
    if not value:
        raise CommandError("Empty datetime/date value.")

    dt = parse_datetime(value)
    if dt is not None:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=UTC)
        return dt.astimezone(UTC)

    d = parse_date(value)
    if d is not None:
        if end_of_day:
            dt2 = datetime.combine(d, datetime.max.time()).replace(microsecond=999999)
        else:
            dt2 = datetime.combine(d, datetime.min.time()).replace(microsecond=0)
        dt2 = timezone.make_aware(dt2, timezone=UTC)
        return dt2.astimezone(UTC)

    raise CommandError("Invalid format. Use ISO datetime or date (e.g. 2025-12-14T10:00:00Z).")


def _resolve_window(days: int, start_raw: str | None, end_raw: str | None) -> SeedWindow:
    now = timezone.now().astimezone(UTC)
    start = _parse_dt_or_date(start_raw, end_of_day=False) if start_raw else None
    end = _parse_dt_or_date(end_raw, end_of_day=True) if end_raw else None

    if start and end:
        pass
    elif start and not end:
        end = now
    elif end and not start:
        start = end - timedelta(days=days)
    else:
        end = now
        start = end - timedelta(days=days)

    if start > end:
        raise CommandError("`start` must be <= `end`.")

    return SeedWindow(start=start, end=end)


def _random_datetime(start: datetime, end: datetime) -> datetime:
    start_ts = start.timestamp()
    end_ts = end.timestamp()
    ts = random.uniform(start_ts, end_ts)
    return datetime.fromtimestamp(ts, tz=UTC)


def _pick_endpoint(service: str, override_endpoints: list[str] | None) -> str:
    if override_endpoints:
        return random.choice(override_endpoints)
    return random.choice(SERVICE_ENDPOINTS.get(service, DEFAULT_ENDPOINTS))


def _pick_method(endpoint: str) -> str:
    return random.choice(ENDPOINT_METHODS.get(endpoint, FALLBACK_METHODS))


def _pick_status(error_rate: float) -> int:
    success_rate = max(0.0, 1.0 - error_rate)
    client_rate = error_rate * 0.5
    roll = random.random()

    if roll < success_rate:
        return random.choice([200, 201, 202, 204])
    if roll < success_rate + client_rate:
        return random.choice([400, 401, 403, 404, 409, 429])
    return random.choice([500, 502, 503, 504])


def _pick_latency(status_code: int) -> int:
    if status_code >= 500:
        return random.randint(200, 1500)
    if status_code >= 400:
        return random.randint(30, 600)
    return random.randint(10, 450)


def _build_event(
    fake: Faker,
    services: list[str],
    override_endpoints: list[str] | None,
    window: SeedWindow,
    error_rate: float,
) -> dict:
    service = random.choice(services)
    endpoint = _pick_endpoint(service, override_endpoints)
    method = _pick_method(endpoint)
    status_code = _pick_status(error_rate)
    latency_ms = _pick_latency(status_code)
    trace_id = fake.uuid4() if random.random() > 0.1 else None
    user_ref = fake.user_name() if random.random() > 0.15 else None

    return {
        "time": _random_datetime(window.start, window.end),
        "service": service,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "trace_id": trace_id,
        "user_ref": user_ref,
        "tags": {
            "seed": True,
            "source": "faker",
            "service": service,
            "endpoint": endpoint,
        },
    }


def _post_events(
    ingest_url: str,
    events: Iterable[dict],
    *,
    insecure: bool,
    timeout: float,
) -> dict:
    payload = json.dumps({"events": list(events)}).encode("utf-8")
    req = urllib.request.Request(
        ingest_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    context = None
    if insecure and ingest_url.startswith("https://"):
        context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, context=context, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CommandError(f"Ingest failed: HTTP {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise CommandError(f"Ingest failed: {exc}") from exc

    if status != 200:
        raise CommandError(f"Ingest failed: HTTP {status} {body}")

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


class Command(BaseCommand):
    help = "Seed ApiRequest rows with Faker-generated events."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1000, help="Number of events to generate.")
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days back from now to seed (ignored if start/end provided).",
        )
        parser.add_argument("--start", help="ISO datetime/date (UTC) for seed window start.")
        parser.add_argument("--end", help="ISO datetime/date (UTC) for seed window end.")
        parser.add_argument(
            "--services",
            default=",".join(DEFAULT_SERVICES),
            help="Comma-separated services list.",
        )
        parser.add_argument(
            "--endpoints",
            default="",
            help="Comma-separated endpoints list (overrides per-service defaults).",
        )
        parser.add_argument(
            "--error-rate",
            type=float,
            default=0.10,
            help="Combined error rate (0..1). Default 0.10 => 5%% 4xx + 5%% 5xx.",
        )
        parser.add_argument("--seed", type=int, default=None, help="Random seed for repeatability.")
        parser.add_argument(
            "--batch-size",
            type=int,
            default=getattr(settings, "APM_INGEST_BATCH_SIZE", 1000),
            help="Batch size for bulk_create or API chunks.",
        )
        parser.add_argument("--truncate", action="store_true", help="Delete all ApiRequest rows.")
        parser.add_argument(
            "--confirm-truncate",
            default="",
            help='Required with --truncate. Set to "yes" to proceed.',
        )
        parser.add_argument(
            "--validate", action="store_true", help="Validate each event via serializer."
        )
        parser.add_argument(
            "--via-api", action="store_true", help="Seed via /api/requests/ingest/."
        )
        parser.add_argument(
            "--base-url",
            default="",
            help="Base URL for API mode (default: BASE_URL or https://127.0.0.1:${PORT}).",
        )
        parser.add_argument(
            "--insecure",
            action="store_true",
            help="Disable SSL verification for API mode (https).",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=30.0,
            help="HTTP timeout (seconds) for API mode.",
        )

    def handle(self, *args, **options):
        count = int(options["count"])
        days = int(options["days"])
        if count <= 0:
            raise CommandError("--count must be > 0.")
        if days <= 0:
            raise CommandError("--days must be > 0.")

        error_rate = float(options["error_rate"])
        if error_rate < 0 or error_rate > 1:
            raise CommandError("--error-rate must be between 0 and 1.")

        services = _parse_csv(options["services"], DEFAULT_SERVICES)
        endpoints_override = _parse_csv(options["endpoints"], []) if options["endpoints"] else None
        window = _resolve_window(days, options.get("start"), options.get("end"))

        if options["truncate"]:
            if str(options.get("confirm_truncate", "")).strip().lower() != "yes":
                raise CommandError('Refusing to truncate without --confirm-truncate "yes".')
            deleted, _ = ApiRequest.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Truncated ApiRequest rows: {deleted}"))

        if options["seed"] is not None:
            random.seed(options["seed"])

        fake = Faker()
        if options["seed"] is not None:
            fake.seed_instance(options["seed"])

        use_api = bool(options["via_api"])
        batch_size = int(options["batch_size"])
        if batch_size <= 0:
            raise CommandError("--batch-size must be > 0.")

        max_events = int(getattr(settings, "APM_INGEST_MAX_EVENTS", 50_000))
        if use_api and batch_size > max_events:
            self.stdout.write(
                self.style.WARNING(
                    f"--batch-size {batch_size} exceeds APM_INGEST_MAX_EVENTS "
                    f"({max_events}); capping."
                )
            )
            batch_size = max_events

        insecure = bool(options["insecure"])
        if not insecure:
            ssl_verify = os.environ.get("SSL_VERIFY", "").strip().lower()
            if ssl_verify in ("0", "false", "no"):
                insecure = True

        inserted = 0
        rejected = 0

        if use_api:
            base_url = options["base_url"] or os.environ.get("BASE_URL")
            if not base_url:
                port = os.environ.get("PORT", "8443")
                base_url = f"https://127.0.0.1:{port}"

            ingest_url = base_url.rstrip("/") + "/api/requests/ingest/?strict=false"
            batch_payload: list[dict] = []

            for _ in range(count):
                event = _build_event(fake, services, endpoints_override, window, error_rate)
                if options["validate"]:
                    ser = ApiRequestIngestItemSerializer(data=event)
                    ser.is_valid(raise_exception=True)
                    event = ser.validated_data

                payload = {
                    **event,
                    "time": event["time"].astimezone(UTC).isoformat().replace("+00:00", "Z"),
                }
                batch_payload.append(payload)

                if len(batch_payload) >= batch_size:
                    response = _post_events(
                        ingest_url, batch_payload, insecure=insecure, timeout=options["timeout"]
                    )
                    inserted += int(response.get("inserted", 0) or 0)
                    rejected += int(response.get("rejected", 0) or 0)
                    batch_payload = []

            if batch_payload:
                response = _post_events(
                    ingest_url, batch_payload, insecure=insecure, timeout=options["timeout"]
                )
                inserted += int(response.get("inserted", 0) or 0)
                rejected += int(response.get("rejected", 0) or 0)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded via API: inserted={inserted}, rejected={rejected}, url={ingest_url}"
                )
            )
            return

        batch: list[ApiRequest] = []
        for idx in range(count):
            event = _build_event(fake, services, endpoints_override, window, error_rate)
            if options["validate"]:
                ser = ApiRequestIngestItemSerializer(data=event)
                ser.is_valid(raise_exception=True)
                event = ser.validated_data

            batch.append(ApiRequest(**event))

            if len(batch) >= batch_size or idx == count - 1:
                with transaction.atomic():
                    ApiRequest.objects.bulk_create(batch, batch_size=batch_size)
                inserted += len(batch)
                batch = []

        self.stdout.write(self.style.SUCCESS(f"Seeded via ORM: inserted={inserted}"))
