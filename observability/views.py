# observability/views.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import transaction
from django_filters import rest_framework as df_filters
from rest_framework import filters as drf_filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import ApiRequest
from .serializers import ApiRequestIngestItemSerializer, ApiRequestSerializer


class NumberInFilter(df_filters.BaseInFilter, df_filters.NumberFilter):
    """Enables filters like ?status_code__in=200,201,204"""


class ApiRequestFilter(df_filters.FilterSet):
    # Time range
    time_after = df_filters.IsoDateTimeFilter(field_name="time", lookup_expr="gte")
    time_before = df_filters.IsoDateTimeFilter(field_name="time", lookup_expr="lte")

    # Common dimensions
    service = df_filters.CharFilter(field_name="service", lookup_expr="iexact")
    endpoint = df_filters.CharFilter(field_name="endpoint", lookup_expr="iexact")
    method = df_filters.CharFilter(field_name="method", lookup_expr="iexact")

    # Status codes
    status_code = df_filters.NumberFilter(field_name="status_code")
    status_code__in = NumberInFilter(field_name="status_code", lookup_expr="in")

    # Latency range
    latency_min = df_filters.NumberFilter(field_name="latency_ms", lookup_expr="gte")
    latency_max = df_filters.NumberFilter(field_name="latency_ms", lookup_expr="lte")

    # Optional identifiers
    trace_id = df_filters.CharFilter(field_name="trace_id", lookup_expr="iexact")
    user_ref = df_filters.CharFilter(field_name="user_ref", lookup_expr="iexact")

    class Meta:
        model = ApiRequest
        fields = [
            "time_after",
            "time_before",
            "service",
            "endpoint",
            "method",
            "status_code",
            "status_code__in",
            "latency_min",
            "latency_max",
            "trace_id",
            "user_ref",
        ]


class ApiRequestViewSet(viewsets.ModelViewSet):
    queryset = ApiRequest.objects.all()
    serializer_class = ApiRequestSerializer

    filter_backends = [
        df_filters.DjangoFilterBackend,
        drf_filters.OrderingFilter,
        drf_filters.SearchFilter,
    ]
    filterset_class = ApiRequestFilter

    ordering_fields = [
        "time",
        "latency_ms",
        "status_code",
        "service",
        "endpoint",
        "method",
    ]
    ordering = ["-time"]

    search_fields = [
        "service",
        "endpoint",
        "trace_id",
        "user_ref",
    ]

    # ----------------------------
    # Step 2 helpers
    # ----------------------------
    def _get_int_qp(
        self,
        request,
        name: str,
        default: int,
        *,
        min_value: int,
        max_value: Optional[int] = None,
    ) -> int:
        raw = request.query_params.get(name)
        if raw is None or raw == "":
            value = default
        else:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                raise ValidationError({name: "Must be an integer."})

        if value < min_value:
            raise ValidationError({name: f"Must be >= {min_value}."})
        if max_value is not None and value > max_value:
            raise ValidationError({name: f"Must be <= {max_value}."})
        return value

    def _get_bool_qp(self, request, name: str, default: bool = False) -> bool:
        raw = request.query_params.get(name)
        if raw is None or raw == "":
            return default

        s = str(raw).strip().lower()
        if s in ("1", "true", "t", "yes", "y", "on"):
            return True
        if s in ("0", "false", "f", "no", "n", "off"):
            return False

        raise ValidationError({name: "Must be a boolean (true/false)."})

    def _parse_ingest_payload(self, data: Any) -> List[Any]:
        """
        Accepts:
          - raw list payload: [{...}, {...}]
          - wrapper payload: {"events": [{...}, {...}]}
        """
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            if "events" not in data:
                raise ValidationError(
                    {"detail": "Expected a list payload or an object with an 'events' list."}
                )
            events = data.get("events")
            if not isinstance(events, list):
                raise ValidationError({"events": "Must be a list of event objects."})
            return events

        raise ValidationError({"detail": "Expected JSON list or object payload."})

    # ----------------------------
    # Step 2 endpoint
    # ----------------------------
    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request, *args, **kwargs):
        settings_max_events = int(getattr(settings, "APM_INGEST_MAX_EVENTS", 50_000))
        settings_max_errors = int(getattr(settings, "APM_INGEST_MAX_ERRORS", 25))
        settings_batch_size = int(getattr(settings, "APM_INGEST_BATCH_SIZE", 1000))

        # Overrides allowed, but cannot exceed settings maxima
        max_events = self._get_int_qp(
            request, "max_events", settings_max_events, min_value=1, max_value=settings_max_events
        )
        max_errors = self._get_int_qp(
            request, "max_errors", settings_max_errors, min_value=0, max_value=settings_max_errors
        )
        batch_size = self._get_int_qp(
            request, "batch_size", settings_batch_size, min_value=1, max_value=max(1, max_events)
        )
        strict = self._get_bool_qp(request, "strict", default=False)

        events = self._parse_ingest_payload(request.data)

        if len(events) > max_events:
            return Response(
                {
                    "detail": f"Too many events: got {len(events)}, max allowed is {max_events}.",
                    "max_events": max_events,
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        validated_rows: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        invalid_found = False

        for idx, item in enumerate(events):
            # tolerate non-dict items: count as invalid, continue
            if not isinstance(item, dict):
                invalid_found = True
                if len(errors) < max_errors:
                    errors.append(
                        {
                            "index": idx,
                            "errors": {"non_field_errors": ["Each event must be a JSON object/dict."]},
                        }
                    )
                continue

            ser = ApiRequestIngestItemSerializer(data=item)
            if ser.is_valid():
                validated_rows.append(ser.validated_data)
            else:
                invalid_found = True
                if len(errors) < max_errors:
                    errors.append({"index": idx, "errors": ser.errors})

        # Strict mode: reject entire request if any invalid item
        if strict and invalid_found:
            return Response(
                {
                    "detail": "Strict mode enabled: payload contains invalid items. Nothing was inserted.",
                    "inserted": 0,
                    "rejected": len(events),
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normal mode: insert only valid rows
        instances: List[ApiRequest] = [ApiRequest(**row) for row in validated_rows]

        inserted = 0
        if instances:
            with transaction.atomic():
                ApiRequest.objects.bulk_create(instances, batch_size=batch_size)
            inserted = len(instances)

        rejected = len(events) - inserted

        return Response(
            {"inserted": inserted, "rejected": rejected, "errors": errors},
            status=status.HTTP_200_OK,
        )
