from __future__ import annotations

from django_filters import rest_framework as df_filters

from .models import ApiRequest


class NumberInFilter(df_filters.BaseInFilter, df_filters.NumberFilter):
    """Enable filters like ?status_code__in=200,201,204."""


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
