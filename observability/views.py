from __future__ import annotations

from datetime import UTC, timedelta
from time import perf_counter
from typing import Any

from django.conf import settings
from django.db import connection
from django.db.utils import ProgrammingError
from django.utils import timezone
from django_filters import rest_framework as df_filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from pgvector.django import CosineDistance
from rest_framework import filters as drf_filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .ai.gemini import GeminiEmbedError, embed_texts
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
from .api.query_params import (
    get_bool_query_param,
    get_datetime_or_date_query_param,
    get_int_query_param,
)
from .filters import ApiRequestFilter
from .guards import postgres_required
from .metrics import apm_ingest_latency_seconds
from .models import ApiRequest, ApiRequestEmbedding
from .serializers import (
    ApiRequestSerializer,
    DailyAggRowSerializer,
    DailyQueryParamsSerializer,
    KpiQueryParamsSerializer,
    SemanticSearchQueryParamsSerializer,
    TopEndpointsQueryParamsSerializer,
)
from .services.ingestion import (
    IngestConfig,
    IngestPayloadTooLarge,
    StrictIngestValidationError,
    ingest_api_requests,
)


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
    # Step 2 endpoint: /api/requests/ingest/
    # ----------------------------
    @extend_schema(
        request=ApiRequestSerializer(many=True),
        responses=OpenApiTypes.OBJECT,
        summary="Bulk-ingest API request events",
    )
    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request, *args, **kwargs):
        ingest_started_at = perf_counter()
        settings_max_events = int(getattr(settings, "APM_INGEST_MAX_EVENTS", 50_000))
        settings_max_errors = int(getattr(settings, "APM_INGEST_MAX_ERRORS", 25))
        settings_batch_size = int(getattr(settings, "APM_INGEST_BATCH_SIZE", 1000))

        try:
            max_events = get_int_query_param(
                request,
                "max_events",
                settings_max_events,
                min_value=1,
                max_value=settings_max_events,
            )
            max_errors = get_int_query_param(
                request,
                "max_errors",
                settings_max_errors,
                min_value=0,
                max_value=settings_max_errors,
            )
            batch_size = get_int_query_param(
                request,
                "batch_size",
                settings_batch_size,
                min_value=1,
                max_value=max(1, max_events),
            )
            strict = get_bool_query_param(request, "strict", default=False)

            config = IngestConfig(
                max_events=max_events,
                max_errors=max_errors,
                batch_size=batch_size,
                strict=strict,
            )
            result = ingest_api_requests(request.data, config=config)
            return Response(result.as_response_data(), status=status.HTTP_200_OK)
        except IngestPayloadTooLarge as exc:
            return Response(exc.as_response_data(), status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        except StrictIngestValidationError as exc:
            return Response(exc.as_response_data(), status=status.HTTP_400_BAD_REQUEST)
        finally:
            apm_ingest_latency_seconds.observe(perf_counter() - ingest_started_at)

    # ----------------------------
    # Step 3 endpoint: /api/requests/hourly/
    # ----------------------------
    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Hourly aggregated metrics")
    @action(detail=False, methods=["get"], url_path="hourly")
    @postgres_required(
        "Hourly analytics requires PostgreSQL + TimescaleDB (hypertable + hourly CAGG)."
    )
    def hourly(self, request, *args, **kwargs):
        limit = get_int_query_param(request, "limit", default=500, min_value=1, max_value=5000)

        start = get_datetime_or_date_query_param(request, "start", end_of_day=False)
        end = get_datetime_or_date_query_param(request, "end", end_of_day=True)

        now = timezone.now().astimezone(UTC)
        if end is None:
            end = now
        if start is None:
            start = end - timedelta(hours=24)

        if start > end:
            raise ValidationError({"detail": "`start` must be <= `end`."})

        service = request.query_params.get("service")
        endpoint = request.query_params.get("endpoint")

        where_clauses: list[str] = ["bucket >= %s", "bucket <= %s"]
        params: list[Any] = [start, end]

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
                    "detail": (
                        "Hourly aggregate view is not available yet. "
                        "Did you apply Step 3 migrations?"
                    ),
                    "hint": "Run: python manage.py migrate",
                    "error": str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        results: list[dict[str, Any]] = []
        for bucket, svc, ep, hits, errors, avg_latency_ms, max_latency_ms in rows:
            if hasattr(bucket, "astimezone"):
                bucket_iso = bucket.astimezone(UTC).isoformat().replace("+00:00", "Z")
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
    @extend_schema(responses=OpenApiTypes.OBJECT, summary="KPIs (requests, error rate, latency)")
    @action(detail=False, methods=["get"], url_path="kpis")
    @postgres_required(
        "KPIs requires PostgreSQL (percentile_cont) and optionally TimescaleDB (CAGG fast-path)."
    )
    def kpis(self, request, *args, **kwargs):
        qp = KpiQueryParamsSerializer(data=request.query_params)
        qp.is_valid(raise_exception=True)
        v = qp.validated_data

        now = timezone.now().astimezone(UTC)
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

        source = select_kpis_source(
            filters=filters_obj, granularity=granularity, error_from=error_from
        )

        # totals/errors/avg/max
        try:
            if source in ("hourly", "daily"):
                totals_sql, totals_params = kpis_from_cagg_sql(
                    granularity=source,  # type: ignore[arg-type]
                    filters=filters_obj,
                )
            else:
                totals_sql, totals_params = kpis_from_raw_sql(
                    filters=filters_obj, error_from=error_from
                )

            with connection.cursor() as cursor:
                cursor.execute(totals_sql, totals_params)
                totals_row = cursor.fetchone()
        except ProgrammingError:
            # Missing CAGG or other SQL issue => raw fallback
            source = "raw"
            totals_sql, totals_params = kpis_from_raw_sql(
                filters=filters_obj, error_from=error_from
            )
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
    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Top endpoints by hits/errors/latency")
    @action(detail=False, methods=["get"], url_path="top-endpoints")
    @postgres_required(
        "Top endpoints requires PostgreSQL (percentile_cont for p95) and "
        "optionally TimescaleDB (CAGG fast-path)."
    )
    def top_endpoints(self, request, *args, **kwargs):
        qp = TopEndpointsQueryParamsSerializer(data=request.query_params)
        qp.is_valid(raise_exception=True)
        v = qp.validated_data

        now = timezone.now().astimezone(UTC)
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

        with_p95 = get_bool_query_param(request, "with_p95", default=False)

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

                items: list[dict[str, Any]] = []
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

            items: list[dict[str, Any]] = []
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
        items: list[dict[str, Any]] = []
        endpoints_list: list[tuple[str, str]] = []
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

            p95_map: dict[tuple[str, str], float] = {}
            for svc, ep, p95_lat in p95_rows:
                if p95_lat is not None:
                    p95_map[(svc, ep)] = float(p95_lat)

            for item in items:
                key = (item["service"], item["endpoint"])
                item["p95_latency_ms"] = p95_map.get(key)

        return Response({"source": source, "results": items}, status=status.HTTP_200_OK)

    # ----------------------------
    # Embeddings: /api/requests/semantic-search/
    # ----------------------------
    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Semantic search over errors (pgvector)")
    @action(detail=False, methods=["get"], url_path="semantic-search")
    @postgres_required("Semantic search requires PostgreSQL + pgvector.")
    def semantic_search(self, request, *args, **kwargs):
        qp = SemanticSearchQueryParamsSerializer(data=request.query_params)
        qp.is_valid(raise_exception=True)
        v = qp.validated_data

        query_text = v["query_text"]
        limit = int(v.get("limit", 20))
        status_from = int(v.get("status_from", 500))
        service = v.get("service")
        endpoint = v.get("endpoint")

        try:
            query_vector = embed_texts([query_text])[0]
        except GeminiEmbedError as exc:
            return Response(
                {"detail": f"Embedding failed: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        qs = ApiRequestEmbedding.objects.select_related("request").filter(
            source=ApiRequestEmbedding.Source.ERROR,
            request__status_code__gte=status_from,
        )
        if service:
            qs = qs.filter(request__service=service)
        if endpoint:
            qs = qs.filter(request__endpoint=endpoint)

        rows = qs.annotate(distance=CosineDistance("embedding", query_vector)).order_by("distance")[
            :limit
        ]

        results = []
        for row in rows:
            req = row.request
            distance = float(row.distance) if row.distance is not None else None
            score = None if distance is None else max(0.0, 1.0 - distance)
            results.append(
                {
                    "id": req.id,
                    "time": req.time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                    "service": req.service,
                    "endpoint": req.endpoint,
                    "method": req.method,
                    "status_code": req.status_code,
                    "latency_ms": req.latency_ms,
                    "distance": distance,
                    "score": score,
                }
            )

        return Response(
            {
                "query": query_text,
                "count": len(results),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

    # ----------------------------
    # Step 4 endpoint: /api/requests/daily/
    # ----------------------------
    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Daily aggregated metrics")
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

        now = timezone.now().astimezone(UTC)
        if end is None:
            end = now
        if start is None:
            start = end - timedelta(days=7)

        if start > end:
            raise ValidationError({"detail": "`start` must be <= `end`."})

        where_clauses: list[str] = ["bucket >= %s", "bucket <= %s"]
        params: list[Any] = [start, end]

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
                    "detail": (
                        "Daily aggregate view is not available yet. "
                        "Did you apply Step 4 migrations?"
                    ),
                    "hint": "Run: python manage.py migrate",
                    "error": str(e),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        items: list[dict[str, Any]] = []
        for bucket, svc, ep, hits, errors, avg_latency_ms, p95_latency_ms, max_latency_ms in rows:
            if bucket is not None:
                if hasattr(bucket, "astimezone"):
                    bucket = bucket.astimezone(UTC)
                elif timezone.is_naive(bucket):
                    bucket = timezone.make_aware(bucket, timezone=UTC)

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

    @extend_schema(responses=OpenApiTypes.OBJECT, summary="Liveness/readiness health check")
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
