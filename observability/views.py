# observability/views.py
from django_filters import rest_framework as df_filters
from rest_framework import viewsets
from rest_framework import filters as drf_filters

from .models import ApiRequest
from .serializers import ApiRequestSerializer


class NumberInFilter(df_filters.BaseInFilter, df_filters.NumberFilter):
    """Enables filters like ?status_code__in=200,201,204"""


class ApiRequestFilter(df_filters.FilterSet):
    # Time range
    time_after = df_filters.IsoDateTimeFilter(field_name="time", lookup_expr="gte")
    time_before = df_filters.IsoDateTimeFilter(field_name="time", lookup_expr="lte")

    # Useful numeric filters
    latency_ms__gte = df_filters.NumberFilter(field_name="latency_ms", lookup_expr="gte")
    latency_ms__lte = df_filters.NumberFilter(field_name="latency_ms", lookup_expr="lte")

    status_code__gte = df_filters.NumberFilter(field_name="status_code", lookup_expr="gte")
    status_code__lte = df_filters.NumberFilter(field_name="status_code", lookup_expr="lte")
    status_code__in = NumberInFilter(field_name="status_code", lookup_expr="in")

    class Meta:
        model = ApiRequest
        fields = [
            "service",
            "endpoint",
            "method",
            "status_code",
            "trace_id",
            "user_ref",
        ]


class ApiRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ApiRequestSerializer
    queryset = ApiRequest.objects.all().order_by("-time")

    # Filtering / ordering / search (works with DRF defaults in settings too)
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
