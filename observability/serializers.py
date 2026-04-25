# observability/serializers.py
from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers

from .models import ApiRequest


class ApiRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiRequest
        fields = [
            "id",
            "time",
            "service",
            "endpoint",
            "method",
            "status_code",
            "latency_ms",
            "trace_id",
            "user_ref",
            "tags",
        ]
        read_only_fields = ["id"]

    def validate_status_code(self, value: int) -> int:
        if value < 100 or value > 599:
            raise serializers.ValidationError("status_code must be a valid HTTP status (100..599).")
        return value

    def validate_latency_ms(self, value: int) -> int:
        if value < 0:
            raise serializers.ValidationError("latency_ms must be >= 0.")
        return value

    def validate_service(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("service cannot be empty.")
        return value

    def validate_endpoint(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("endpoint cannot be empty.")
        return value

    def validate_tags(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("tags must be a JSON object (dictionary).")
        return value


class ApiRequestIngestItemSerializer(ApiRequestSerializer):
    """
    Validates ONE ingested event.
    Reuses the exact same validation rules as CRUD by inheriting ApiRequestSerializer.
    """

    class Meta(ApiRequestSerializer.Meta):
        # Same as CRUD minus "id" (ingest payload shouldn't send it)
        fields = [
            "time",
            "service",
            "endpoint",
            "method",
            "status_code",
            "latency_ms",
            "trace_id",
            "user_ref",
            "tags",
        ]
        read_only_fields = []

        # Make optional fields optional for ingestion payloads
        extra_kwargs = {
            "trace_id": {"required": False, "allow_null": True, "allow_blank": True},
            "user_ref": {"required": False, "allow_null": True, "allow_blank": True},
            "tags": {"required": False},
        }


# ----------------------------
# Step 4: Query params validation
# ----------------------------
class IsoDateTimeOrDateField(serializers.Field):
    """
    Accepts either:
      - ISO datetime (e.g. 2025-12-14T10:00:00Z)
      - ISO date (e.g. 2025-12-14)

    Returns:
      - aware datetime in UTC

    If a date is provided:
      - end_of_day=False -> 00:00:00.000000Z
      - end_of_day=True  -> 23:59:59.999999Z
    """

    default_error_messages = {
        "invalid": "Must be an ISO datetime or date (e.g. 2025-12-14T10:00:00Z or 2025-12-14)."
    }

    def __init__(self, *args, end_of_day: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.end_of_day = end_of_day

    def to_internal_value(self, data: Any) -> datetime | None:
        if data is None or data == "":
            return None

        s = str(data).strip()

        # Try datetime first
        dt = parse_datetime(s)
        if dt is not None:
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone=UTC)
            return dt.astimezone(UTC)

        # Then try date
        d = parse_date(s)
        if d is not None:
            if self.end_of_day:
                dt2 = datetime.combine(d, time(23, 59, 59, 999999))
            else:
                dt2 = datetime.combine(d, time(0, 0, 0))
            dt2 = timezone.make_aware(dt2, timezone=UTC)
            return dt2.astimezone(UTC)

        self.fail("invalid")

    def to_representation(self, value: Any) -> Any:
        # Not needed for query params usage, but keep it sane
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return str(value)


class DailyQueryParamsSerializer(serializers.Serializer):
    """
    Validates query params for GET /api/requests/daily/

    - start/end can be ISO datetime or ISO date
    - ensures start <= end
    - validates limit bounds
    """

    start = IsoDateTimeOrDateField(required=False, allow_null=True, end_of_day=False)
    end = IsoDateTimeOrDateField(required=False, allow_null=True, end_of_day=True)

    service = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    endpoint = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)

    limit = serializers.IntegerField(required=False, default=500, min_value=1, max_value=5000)

    def validate(self, attrs):
        start = attrs.get("start")
        end = attrs.get("end")

        if start is not None and end is not None and start > end:
            raise serializers.ValidationError({"detail": "`start` must be <= `end`."})

        return attrs


# ----------------------------
# Step 5: KPI / Top endpoints query params validation
# ----------------------------
class KpiQueryParamsSerializer(serializers.Serializer):
    """
    Validates query params for GET /api/requests/kpis/

    Supported:
      - start/end (ISO datetime or ISO date)
      - service, endpoint, method
      - granularity: auto|hourly|daily
      - error_from: HTTP status threshold for "error" (default 500)

    Ensures:
      - start <= end
      - clean error messages on invalid inputs
    """

    start = IsoDateTimeOrDateField(required=False, allow_null=True, end_of_day=False)
    end = IsoDateTimeOrDateField(required=False, allow_null=True, end_of_day=True)

    service = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    endpoint = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    method = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)

    granularity = serializers.ChoiceField(
        required=False,
        default="auto",
        choices=("auto", "hourly", "daily"),
    )

    error_from = serializers.IntegerField(required=False, default=500, min_value=100, max_value=599)

    def validate_method(self, value: str) -> str:
        v = value.strip().upper()
        # allow any token, but prevent empty/whitespace
        if not v:
            raise serializers.ValidationError("method cannot be empty.")
        return v

    def validate(self, attrs):
        start = attrs.get("start")
        end = attrs.get("end")
        if start is not None and end is not None and start > end:
            raise serializers.ValidationError({"detail": "`start` must be <= `end`."})
        return attrs


class TopEndpointsQueryParamsSerializer(serializers.Serializer):
    """
    Validates query params for GET /api/requests/top-endpoints/

    Supported:
      - start/end (ISO datetime or ISO date)
      - service, endpoint, method
      - granularity: auto|hourly|daily
      - error_from: HTTP status threshold for "error" (default 500)
      - limit: number of rows to return (default 20, max 200)
      - sort_by: hits|errors|error_rate|avg_latency_ms|p95_latency_ms|max_latency_ms
      - direction: asc|desc

    Ensures:
      - start <= end
      - limit/sort/direction constraints enforced
    """

    start = IsoDateTimeOrDateField(required=False, allow_null=True, end_of_day=False)
    end = IsoDateTimeOrDateField(required=False, allow_null=True, end_of_day=True)

    service = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    endpoint = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    method = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)

    granularity = serializers.ChoiceField(
        required=False,
        default="auto",
        choices=("auto", "hourly", "daily"),
    )

    error_from = serializers.IntegerField(required=False, default=500, min_value=100, max_value=599)

    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=200)

    sort_by = serializers.ChoiceField(
        required=False,
        default="hits",
        choices=(
            "hits",
            "errors",
            "error_rate",
            "avg_latency_ms",
            "p95_latency_ms",
            "max_latency_ms",
        ),
    )

    direction = serializers.ChoiceField(required=False, default="desc", choices=("asc", "desc"))

    # Optional: compute p95 per returned endpoint when using CAGG fast-path
    with_p95 = serializers.BooleanField(required=False, default=False)

    def validate_method(self, value: str) -> str:
        v = value.strip().upper()
        if not v:
            raise serializers.ValidationError("method cannot be empty.")
        return v

    def validate(self, attrs):
        start = attrs.get("start")
        end = attrs.get("end")
        if start is not None and end is not None and start > end:
            raise serializers.ValidationError({"detail": "`start` must be <= `end`."})
        return attrs


class SemanticSearchQueryParamsSerializer(serializers.Serializer):
    """
    Validates query params for GET /api/requests/semantic-search/
    """

    q = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    query = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    limit = serializers.IntegerField(required=False, default=20, min_value=1, max_value=200)
    status_from = serializers.IntegerField(
        required=False, default=500, min_value=100, max_value=599
    )
    service = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    endpoint = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)

    def validate(self, attrs):
        q = attrs.get("q") or attrs.get("query")
        if not q:
            raise serializers.ValidationError({"detail": "Missing query. Use ?q=... or ?query=..."})
        attrs["query_text"] = q
        return attrs


# ----------------------------
# Step 4: Daily analytics response serializer
# ----------------------------
class DailyAggRowSerializer(serializers.Serializer):
    """
    Response schema for /api/requests/daily/

    Note:
      - bucket is returned as ISO string via DRF DateTimeField.
      - p95_latency_ms may be null if the CAGG was created without p95 support.
    """

    bucket = serializers.DateTimeField()
    service = serializers.CharField()
    endpoint = serializers.CharField()

    hits = serializers.IntegerField()
    errors = serializers.IntegerField()

    avg_latency_ms = serializers.FloatField(allow_null=True)
    p95_latency_ms = serializers.FloatField(allow_null=True, required=False)
    max_latency_ms = serializers.IntegerField(allow_null=True, required=False)
