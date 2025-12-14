# observability/views.py
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone as dt_timezone
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import connection, transaction
from django.db.utils import ProgrammingError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django_filters import rest_framework as df_filters
from rest_framework import filters as drf_filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response

from .analytics.sql import (
    AnalyticsFilters,
    kpis_from_cagg_sql,
    kpis_from_raw_sql,
    p95_by_endpoints_from_raw_sql,
    p95_global_from_raw_sql,
    select_kpis_source,
    select_top_endpoints_source,
    top_endpoints_from_cagg_sql,
    top_endpoints_from_raw_sql,
)
from .guards import postgres_required
from .models import ApiRequest
from .serializers import (
    ApiRequestIngestItemSerializer,
    ApiRequestSerializer,
    DailyAggRowSerializer,
    DailyQueryParamsSerializer,
    KpiQueryParamsSerializer,
    TopEndpointsQueryParamsSerializer,
)


class NumberInFilter(df_filters.BaseInFilter, df_filters.NumberFilter):
    """Enables filters like ?status_code__in=200,201,204"""


class ApiRequestFilter(df_filters.FilterSet):
    time_after = df_filters.IsoDateTimeFilter(field_name="time", lookup_expr="gte")
    time_before = df_filters.IsoDateTimeFilter(field_name="time", lookup_expr="lte")

    service = df_filters.CharFilter(field_name="service", lookup_expr="iexact")
    endpoint = df_filters.CharFilter(field_name="endpoint", lookup_expr="iexact")
    method = df_filters.CharFilter(field_name="method", lookup_expr="iexact")

    status_code = df_filters.NumberFilter(field_name="status_code")
    status_code__in = NumberInFilter(field_name="status_code", lookup_expr="in")

    latency_min = df_filters.NumberFilter(field_name="latency_ms", lookup_expr="gte")
    latency_max = df_filters.NumberFilter(field_name="latency_ms", lookup_expr="lte")

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
    # Helpers (query params)
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

    def _get_dt_or_date_qp(self, request, name: str, *, end_of_day: bool = False):
        raw = request.query_params.get(name)
        if raw is None or raw == "":
            return None

        s = str(raw).strip()

        dt = parse_datetime(s)
        if dt is not None:
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone=dt_timezone.utc)
            return dt.astimezone(dt_timezone.utc)

        d = parse_date(s)
        if d is not None:
            if end_of_day:
                dt2 = datetime.combine(d, time(23, 59, 59, 999999))
            else:
                dt2 = datetime.combine(d, time(0, 0, 0))
            dt2 = timezone.make_aware(dt2, timezone=dt_timezone.utc)
            return dt2.astimezone(dt_timezone.utc)

        raise ValidationError(
            {name: "Must be an ISO datetime or date (e.g. 2025-12-14T10:00:00Z or 2025-12-14)."}
        )

    def _parse_ingest_payload(self, data: Any) -> List[Any]:
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
    # Step 2 endpoint: /api/requests/ingest/
    # ----------------------------
    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request, *args, **kwargs):
        settings_max_events = int(getattr(settings, "APM_INGEST_MAX_EVENTS", 50_000))
        settings_max_errors = int(getattr(settings, "APM_INGEST_MAX_ERRORS", 25))
        settings_batch_size = int(getattr(settings, "APM_INGEST_BATCH_SIZE", 1000))

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

    # ----------------------------
    # Step 3 endpoint: /api/requests/hourly/
    # ----------------------------
    @action(detail=False, methods=["get"], url_path="hourly")
    @postgres_required("Hourly analytics requires PostgreSQL + TimescaleDB (hypertable + hourly CAGG).")
    def hourly(self, request, *args, **kwargs):
        limit = self._get_int_qp(request, "limit", default=500, min_value=1, max_value=5000)

        start = self._get_dt_or_date_qp(request, "start", end_of_day=False)
        end = self._get_dt_or_date_qp(request, "end", end_of_day=True)

        now = timezone.now().astimezone(dt_timezone.utc)
        if end is None:
            end = now
        if start is None:
            start = end - timedelta(hours=24)

        if start > end:
            raise ValidationError({"detail": "`start` must be <= `end`."})

        service = request.query_params.get("service")
        endpoint = request.query_params.get("endpoint")

        where_clauses: List[str] = ["bucket >= %s", "bucket <= %s"]
        params: List[Any] = [start, end]

        if service:
            where_clauses.append("service = %s")
            params.append(service)

        if endpoint:
            where_clauses.append("endpoint = %s")
            params.append(endpoint)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT
                bucket,
                service,
                endpoint,
                hits,
                errors,
                avg_latency_ms,
                max_latency_ms
            FROM apirequest_hourly
            WHERE {where_sql}
            ORDER BY bucket DESC, service ASC, endpoint ASC
            LIMIT %s
        """
        params.append(limit)

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        except ProgrammingError as e:
            return Response(
                {
                    "detail": "Hourly aggregate view is not available yet. Did you apply Step 3 migrations?",
                    "hint": "Run: python manage.py migrate",
                    "error": str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        results: List[Dict[str, Any]] = []
        for bucket, svc, ep, hits, errors, avg_latency_ms, max_latency_ms in rows:
            if hasattr(bucket, "astimezone"):
                bucket_iso = bucket.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
            else:
                bucket_iso = str(bucket)

            results.append(
                {
                    "bucket": bucket_iso,
                    "service": svc,
                    "endpoint": ep,
                    "hits": int(hits) if hits is not None else 0,
                    "errors": int(errors) if errors is not None else 0,
                    "avg_latency_ms": float(avg_latency_ms) if avg_latency_ms is not None else None,
                    "max_latency_ms": int(max_latency_ms) if max_latency_ms is not None else None,
                }
            )

        return Response(results, status=status.HTTP_200_OK)

    # ----------------------------
    # Step 5 endpoint: /api/requests/kpis/
    # ----------------------------
    @action(detail=False, methods=["get"], url_path="kpis")
    @postgres_required(
        "KPIs requires PostgreSQL (percentile_cont) and optionally TimescaleDB (CAGG fast-path)."
    )
    def kpis(self, request, *args, **kwargs):
        qp = KpiQueryParamsSerializer(data=request.query_params)
        qp.is_valid(raise_exception=True)
        v = qp.validated_data

        now = timezone.now().astimezone(dt_timezone.utc)
        end = v.get("end") or now
        start = v.get("start") or (end - timedelta(hours=24))

        if start > end:
            raise ValidationError({"detail": "`start` must be <= `end`."})

        service = v.get("service")
        endpoint = v.get("endpoint")
        method = v.get("method")
        granularity = v.get("granularity", "auto")
        error_from = int(v.get("error_from", 500))

        filters_obj = AnalyticsFilters(
            start=start,
            end=end,
            service=service,
            endpoint=endpoint,
            method=method,
        )

        source = select_kpis_source(filters=filters_obj, granularity=granularity, error_from=error_from)

        # totals/errors/avg/max
        try:
            if source in ("hourly", "daily"):
                totals_sql, totals_params = kpis_from_cagg_sql(
                    granularity=source,  # type: ignore[arg-type]
                    filters=filters_obj,
                )
            else:
                totals_sql, totals_params = kpis_from_raw_sql(filters=filters_obj, error_from=error_from)

            with connection.cursor() as cursor:
                cursor.execute(totals_sql, totals_params)
                totals_row = cursor.fetchone()
        except ProgrammingError:
            # Missing CAGG or other SQL issue => raw fallback
            source = "raw"
            totals_sql, totals_params = kpis_from_raw_sql(filters=filters_obj, error_from=error_from)
            with connection.cursor() as cursor:
                cursor.execute(totals_sql, totals_params)
                totals_row = cursor.fetchone()

        if not totals_row:
            hits = 0
            errors = 0
            error_rate = 0.0
            avg_latency_ms = None
            max_latency_ms = None
        else:
            hits, errors, error_rate, avg_latency_ms, max_latency_ms = totals_row
            hits = int(hits or 0)
            errors = int(errors or 0)
            error_rate = float(error_rate or 0.0)
            avg_latency_ms = float(avg_latency_ms) if avg_latency_ms is not None else None
            max_latency_ms = int(max_latency_ms) if max_latency_ms is not None else None

        # p95 is always computed from RAW for correctness
        p95_latency_ms = None
        p95_sql, p95_params = p95_global_from_raw_sql(filters=filters_obj)
        with connection.cursor() as cursor:
            cursor.execute(p95_sql, p95_params)
            row = cursor.fetchone()
            if row:
                p95_latency_ms = float(row[0]) if row[0] is not None else None

        return Response(
            {
                "hits": hits,
                "errors": errors,
                "error_rate": error_rate,
                "avg_latency_ms": avg_latency_ms,
                "p95_latency_ms": p95_latency_ms,
                "max_latency_ms": max_latency_ms,
                "source": source,
            },
            status=status.HTTP_200_OK,
        )

    # ----------------------------
    # Step 5 endpoint: /api/requests/top-endpoints/
    # ----------------------------
    @action(detail=False, methods=["get"], url_path="top-endpoints")
    @postgres_required(
        "Top endpoints requires PostgreSQL (percentile_cont for p95) and optionally TimescaleDB (CAGG fast-path)."
    )
    def top_endpoints(self, request, *args, **kwargs):
        qp = TopEndpointsQueryParamsSerializer(data=request.query_params)
        qp.is_valid(raise_exception=True)
        v = qp.validated_data

        now = timezone.now().astimezone(dt_timezone.utc)
        end = v.get("end") or now
        start = v.get("start") or (end - timedelta(hours=24))
        if start > end:
            raise ValidationError({"detail": "`start` must be <= `end`."})

        service = v.get("service")
        endpoint = v.get("endpoint")
        method = v.get("method")
        granularity = v.get("granularity", "auto")
        error_from = int(v.get("error_from", 500))

        limit = int(v.get("limit", 20))
        sort_by = v.get("sort_by", "hits")
        direction = v.get("direction", "desc")

        with_p95 = self._get_bool_qp(request, "with_p95", default=False)

        filters_obj = AnalyticsFilters(
            start=start,
            end=end,
            service=service,
            endpoint=endpoint,
            method=method,
        )

        source = select_top_endpoints_source(
            filters=filters_obj,
            granularity=granularity,
            error_from=error_from,
            sort_by=sort_by,
        )

        try:
            if source == "raw":
                include_p95 = with_p95 or (sort_by == "p95_latency_ms")
                sql, params = top_endpoints_from_raw_sql(
                    filters=filters_obj,
                    error_from=error_from,
                    limit=limit,
                    sort_by=sort_by,
                    direction=direction,
                    include_p95=include_p95,
                )
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()

                items: List[Dict[str, Any]] = []
                for r in rows:
                    if include_p95:
                        svc, ep, hits, errors, err_rate, avg_lat, max_lat, p95_lat = r
                    else:
                        svc, ep, hits, errors, err_rate, avg_lat, max_lat = r
                        p95_lat = None

                    items.append(
                        {
                            "service": svc,
                            "endpoint": ep,
                            "hits": int(hits or 0),
                            "errors": int(errors or 0),
                            "error_rate": float(err_rate or 0.0),
                            "avg_latency_ms": float(avg_lat) if avg_lat is not None else None,
                            "p95_latency_ms": float(p95_lat) if p95_lat is not None else None,
                            "max_latency_ms": int(max_lat) if max_lat is not None else None,
                        }
                    )

                return Response({"source": source, "results": items}, status=status.HTTP_200_OK)

            # hourly/daily CAGG fast-path
            sql, params = top_endpoints_from_cagg_sql(
                granularity=source,  # type: ignore[arg-type]
                filters=filters_obj,
                limit=limit,
                sort_by=sort_by,
                direction=direction,
            )
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()

        except ProgrammingError:
            # Missing CAGG -> raw fallback
            source = "raw"
            include_p95 = with_p95
            sql, params = top_endpoints_from_raw_sql(
                filters=filters_obj,
                error_from=500,  # caggs are defined for >=500; fallback uses 500 for consistency
                limit=limit,
                sort_by=sort_by if sort_by != "p95_latency_ms" else "hits",
                direction=direction,
                include_p95=include_p95,
            )
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()

            items: List[Dict[str, Any]] = []
            for r in rows:
                if include_p95:
                    svc, ep, hits, errors, err_rate, avg_lat, max_lat, p95_lat = r
                else:
                    svc, ep, hits, errors, err_rate, avg_lat, max_lat = r
                    p95_lat = None

                items.append(
                    {
                        "service": svc,
                        "endpoint": ep,
                        "hits": int(hits or 0),
                        "errors": int(errors or 0),
                        "error_rate": float(err_rate or 0.0),
                        "avg_latency_ms": float(avg_lat) if avg_lat is not None else None,
                        "p95_latency_ms": float(p95_lat) if p95_lat is not None else None,
                        "max_latency_ms": int(max_lat) if max_lat is not None else None,
                    }
                )
            return Response({"source": source, "results": items}, status=status.HTTP_200_OK)

        # Parse CAGG rows
        items: List[Dict[str, Any]] = []
        endpoints_list: List[tuple[str, str]] = []
        for svc, ep, hits, errors, err_rate, avg_lat, max_lat in rows:
            endpoints_list.append((svc, ep))
            items.append(
                {
                    "service": svc,
                    "endpoint": ep,
                    "hits": int(hits or 0),
                    "errors": int(errors or 0),
                    "error_rate": float(err_rate or 0.0),
                    "avg_latency_ms": float(avg_lat) if avg_lat is not None else None,
                    "p95_latency_ms": None,
                    "max_latency_ms": int(max_lat) if max_lat is not None else None,
                }
            )

        # Optional p95 for returned endpoints only
        if with_p95 and endpoints_list:
            p95_sql, p95_params = p95_by_endpoints_from_raw_sql(
                filters=AnalyticsFilters(
                    start=start,
                    end=end,
                    service=service,
                    endpoint=endpoint,
                    method=None,  # method would have forced raw
                ),
                endpoints=endpoints_list,
            )
            with connection.cursor() as cursor:
                cursor.execute(p95_sql, p95_params)
                p95_rows = cursor.fetchall()

            p95_map: Dict[tuple[str, str], float] = {}
            for svc, ep, p95_lat in p95_rows:
                if p95_lat is not None:
                    p95_map[(svc, ep)] = float(p95_lat)

            for item in items:
                key = (item["service"], item["endpoint"])
                item["p95_latency_ms"] = p95_map.get(key)

        return Response({"source": source, "results": items}, status=status.HTTP_200_OK)

    # ----------------------------
    # Step 4 endpoint: /api/requests/daily/
    # ----------------------------
    @action(detail=False, methods=["get"], url_path="daily")
    @postgres_required("Daily analytics requires PostgreSQL + TimescaleDB (daily CAGG).")
    def daily(self, request, *args, **kwargs):
        qp = DailyQueryParamsSerializer(data=request.query_params)
        qp.is_valid(raise_exception=True)
        v = qp.validated_data

        limit = v.get("limit", 500)
        start = v.get("start")
        end = v.get("end")
        service = v.get("service")
        endpoint = v.get("endpoint")

        now = timezone.now().astimezone(dt_timezone.utc)
        if end is None:
            end = now
        if start is None:
            start = end - timedelta(days=7)

        if start > end:
            raise ValidationError({"detail": "`start` must be <= `end`."})

        where_clauses: List[str] = ["bucket >= %s", "bucket <= %s"]
        params: List[Any] = [start, end]

        if service:
            where_clauses.append("service = %s")
            params.append(service)

        if endpoint:
            where_clauses.append("endpoint = %s")
            params.append(endpoint)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT
                bucket,
                service,
                endpoint,
                hits,
                errors,
                avg_latency_ms,
                p95_latency_ms,
                max_latency_ms
            FROM apirequest_daily
            WHERE {where_sql}
            ORDER BY bucket DESC, service ASC, endpoint ASC
            LIMIT %s
        """
        params.append(limit)

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        except ProgrammingError as e:
            return Response(
                {
                    "detail": "Daily aggregate view is not available yet. Did you apply Step 4 migrations?",
                    "hint": "Run: python manage.py migrate",
                    "error": str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        items: List[Dict[str, Any]] = []
        for bucket, svc, ep, hits, errors, avg_latency_ms, p95_latency_ms, max_latency_ms in rows:
            if bucket is not None:
                if hasattr(bucket, "astimezone"):
                    bucket = bucket.astimezone(dt_timezone.utc)
                elif timezone.is_naive(bucket):
                    bucket = timezone.make_aware(bucket, timezone=dt_timezone.utc)

            items.append(
                {
                    "bucket": bucket,
                    "service": svc,
                    "endpoint": ep,
                    "hits": int(hits) if hits is not None else 0,
                    "errors": int(errors) if errors is not None else 0,
                    "avg_latency_ms": float(avg_latency_ms) if avg_latency_ms is not None else None,
                    "p95_latency_ms": float(p95_latency_ms) if p95_latency_ms is not None else None,
                    "max_latency_ms": int(max_latency_ms) if max_latency_ms is not None else None,
                }
            )

        out = DailyAggRowSerializer(items, many=True)
        return Response(out.data, status=status.HTTP_200_OK)


class HealthView(APIView):
    """
    GET /api/health/
    Optional DB check: /api/health/?db=1  (or db=true/yes/on)
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        db_flag = (request.query_params.get("db") or "").strip().lower()
        check_db = db_flag in {"1", "true", "yes", "y", "on"}

        if not check_db:
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
        except Exception as exc:
            return Response(
                {"status": "error", "db": "unavailable", "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"status": "ok", "db": "ok"}, status=status.HTTP_200_OK)
