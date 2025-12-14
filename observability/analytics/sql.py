# observability/analytics/sql.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Literal, Optional, Sequence, Tuple

Granularity = Literal["hourly", "daily"]
GranularityParam = Literal["auto", "hourly", "daily"]
TableKind = Literal["raw", "hourly", "daily"]

RAW_TABLE = "observability_apirequest"
HOURLY_CAGG = "apirequest_hourly"
DAILY_CAGG = "apirequest_daily"

DEFAULT_AUTO_HOURLY_MAX_HOURS = 48

# ----------------------------
# Filters / where-clause builder
# ----------------------------
@dataclass(frozen=True)
class AnalyticsFilters:
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    service: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None  # raw-only


def build_where_clause(
    filters: AnalyticsFilters,
    *,
    kind: TableKind,
    time_column: str | None = None,
) -> Tuple[str, List[object]]:
    """
    Returns: ("WHERE ...", [params]) or ("", []).
    Uses parameter placeholders (%s) only (safe).
    """
    clauses: List[str] = []
    params: List[object] = []

    if kind == "raw":
        tcol = time_column or "time"
    else:
        tcol = time_column or "bucket"

    if filters.start is not None:
        clauses.append(f"{tcol} >= %s")
        params.append(filters.start)

    if filters.end is not None:
        clauses.append(f"{tcol} <= %s")
        params.append(filters.end)

    if filters.service:
        clauses.append("service = %s")
        params.append(filters.service)

    if filters.endpoint:
        clauses.append("endpoint = %s")
        params.append(filters.endpoint)

    if kind == "raw" and filters.method:
        clauses.append("method = %s")
        params.append(filters.method)

    if not clauses:
        return "", params

    return "WHERE " + " AND ".join(clauses), params


# ----------------------------
# Source selection helpers (Step 6)
# ----------------------------
def _auto_granularity(
    start: Optional[datetime],
    end: Optional[datetime],
    *,
    hourly_max_hours: int = DEFAULT_AUTO_HOURLY_MAX_HOURS,
) -> Granularity:
    """
    If range <= hourly_max_hours => hourly else daily.
    If start/end missing, default daily (safer).
    """
    if start is None or end is None:
        return "daily"
    if end < start:
        # views validate start<=end; default daily here just in case.
        return "daily"
    if (end - start) <= timedelta(hours=hourly_max_hours):
        return "hourly"
    return "daily"


def select_kpis_source(
    *,
    filters: AnalyticsFilters,
    granularity: GranularityParam = "auto",
    error_from: int = 500,
    hourly_max_hours: int = DEFAULT_AUTO_HOURLY_MAX_HOURS,
) -> TableKind:
    """
    KPIs (totals/errors/avg/max) can use CAGGs only when:
      - method is NOT used (method is raw-only)
      - error_from == 500 (caggs are baked with status_code >= 500)
    Otherwise raw.
    """
    if filters.method:
        return "raw"
    if error_from != 500:
        return "raw"

    if granularity == "daily":
        return "daily"
    if granularity == "hourly":
        return "hourly"

    return _auto_granularity(filters.start, filters.end, hourly_max_hours=hourly_max_hours)


def select_top_endpoints_source(
    *,
    filters: AnalyticsFilters,
    granularity: GranularityParam = "auto",
    error_from: int = 500,
    sort_by: str = "hits",
    hourly_max_hours: int = DEFAULT_AUTO_HOURLY_MAX_HOURS,
) -> TableKind:
    """
    Top endpoints can use CAGGs only when:
      - method is NOT used
      - error_from == 500
      - sort_by != p95_latency_ms (since caggs don't compute p95 here)
    Otherwise raw.
    """
    if filters.method:
        return "raw"
    if error_from != 500:
        return "raw"
    if sort_by == "p95_latency_ms":
        return "raw"

    if granularity == "daily":
        return "daily"
    if granularity == "hourly":
        return "hourly"

    return _auto_granularity(filters.start, filters.end, hourly_max_hours=hourly_max_hours)


# ----------------------------
# KPI SQL builders
# ----------------------------
def kpis_from_cagg_sql(
    *,
    granularity: Granularity,
    filters: AnalyticsFilters,
) -> Tuple[str, List[object]]:
    """
    KPI totals/errors/avg/max using Timescale CAGGs (fast).
    NOTE: error threshold is baked into caggs as status_code >= 500.
    NOTE: p95 is NOT computed here (use raw builder below).
    """
    view = HOURLY_CAGG if granularity == "hourly" else DAILY_CAGG
    where_sql, params = build_where_clause(filters, kind=granularity, time_column="bucket")

    sql = f"""
    SELECT
        COALESCE(SUM(hits), 0)::bigint AS hits,
        COALESCE(SUM(errors), 0)::bigint AS errors,
        CASE
            WHEN COALESCE(SUM(hits), 0) > 0
            THEN (SUM(errors)::double precision / SUM(hits)::double precision)
            ELSE 0::double precision
        END AS error_rate,
        CASE
            WHEN COALESCE(SUM(hits), 0) > 0
            THEN (SUM(avg_latency_ms * hits)::double precision / SUM(hits)::double precision)
            ELSE NULL::double precision
        END AS avg_latency_ms,
        MAX(max_latency_ms)::integer AS max_latency_ms
    FROM {view}
    {where_sql}
    """
    return sql.strip(), params


def kpis_from_raw_sql(
    *,
    filters: AnalyticsFilters,
    error_from: int = 500,
) -> Tuple[str, List[object]]:
    """
    KPI totals/errors/avg/max using raw hypertable (fallback path).
    Supports custom error_from and method.
    """
    where_sql, params = build_where_clause(filters, kind="raw", time_column="time")

    sql = f"""
    SELECT
        COUNT(*)::bigint AS hits,
        COUNT(*) FILTER (WHERE status_code >= %s)::bigint AS errors,
        CASE
            WHEN COUNT(*) > 0
            THEN (COUNT(*) FILTER (WHERE status_code >= %s)::double precision / COUNT(*)::double precision)
            ELSE 0::double precision
        END AS error_rate,
        AVG(latency_ms)::double precision AS avg_latency_ms,
        MAX(latency_ms)::integer AS max_latency_ms
    FROM {RAW_TABLE}
    {where_sql}
    """
    params2 = [error_from, error_from] + params
    return sql.strip(), params2


def p95_global_from_raw_sql(
    *,
    filters: AnalyticsFilters,
) -> Tuple[str, List[object]]:
    """
    Global p95 over raw table (correct).
    """
    where_sql, params = build_where_clause(filters, kind="raw", time_column="time")

    sql = f"""
    SELECT
        (percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms))::double precision AS p95_latency_ms
    FROM {RAW_TABLE}
    {where_sql}
    """
    return sql.strip(), params


def p95_by_endpoints_from_raw_sql(
    *,
    filters: AnalyticsFilters,
    endpoints: Sequence[Tuple[str, str]],
) -> Tuple[str, List[object]]:
    """
    p95 per (service, endpoint) for a *given list* of endpoints (safe, fast enough).
    Uses a VALUES table to avoid unsafe SQL concatenation.
    """
    if not endpoints:
        return (
            "SELECT NULL::text AS service, NULL::text AS endpoint, NULL::double precision AS p95_latency_ms WHERE FALSE",
            [],
        )

    values_rows = ", ".join(["(%s, %s)"] * len(endpoints))
    values_params: List[object] = []
    for svc, ep in endpoints:
        values_params.append(svc)
        values_params.append(ep)

    where_sql, where_params = build_where_clause(filters, kind="raw", time_column="time")

    sql = f"""
    WITH targets(service, endpoint) AS (
        VALUES {values_rows}
    )
    SELECT
        t.service,
        t.endpoint,
        (percentile_cont(0.95) WITHIN GROUP (ORDER BY r.latency_ms))::double precision AS p95_latency_ms
    FROM targets t
    JOIN {RAW_TABLE} r
      ON r.service = t.service
     AND r.endpoint = t.endpoint
    {where_sql.replace("service = %s", "r.service = %s").replace("endpoint = %s", "r.endpoint = %s").replace("method = %s", "r.method = %s").replace("time", "r.time")}
    GROUP BY t.service, t.endpoint
    """
    params = values_params + where_params
    return sql.strip(), params


# ----------------------------
# Top endpoints SQL builders
# ----------------------------
_CAGG_SORT_ALLOWLIST = {
    "hits": "hits",
    "errors": "errors",
    "error_rate": "error_rate",
    "avg_latency_ms": "avg_latency_ms",
    "max_latency_ms": "max_latency_ms",
}


def top_endpoints_from_cagg_sql(
    *,
    granularity: Granularity,
    filters: AnalyticsFilters,
    limit: int = 20,
    sort_by: str = "hits",
    direction: Literal["asc", "desc"] = "desc",
) -> Tuple[str, List[object]]:
    """
    Top endpoints using CAGGs (fast).
    NOTE: Does NOT compute p95 here.
    """
    view = HOURLY_CAGG if granularity == "hourly" else DAILY_CAGG
    where_sql, params = build_where_clause(filters, kind=granularity, time_column="bucket")

    sort_col = _CAGG_SORT_ALLOWLIST.get(sort_by, "hits")
    dir_sql = "ASC" if direction.lower() == "asc" else "DESC"

    sql = f"""
    SELECT
        service,
        endpoint,
        COALESCE(SUM(hits), 0)::bigint AS hits,
        COALESCE(SUM(errors), 0)::bigint AS errors,
        CASE
            WHEN COALESCE(SUM(hits), 0) > 0
            THEN (SUM(errors)::double precision / SUM(hits)::double precision)
            ELSE 0::double precision
        END AS error_rate,
        CASE
            WHEN COALESCE(SUM(hits), 0) > 0
            THEN (SUM(avg_latency_ms * hits)::double precision / SUM(hits)::double precision)
            ELSE NULL::double precision
        END AS avg_latency_ms,
        MAX(max_latency_ms)::integer AS max_latency_ms
    FROM {view}
    {where_sql}
    GROUP BY service, endpoint
    ORDER BY {sort_col} {dir_sql}, service ASC, endpoint ASC
    LIMIT %s
    """
    return sql.strip(), params + [limit]


_RAW_SORT_ALLOWLIST = {
    "hits": "hits",
    "errors": "errors",
    "error_rate": "error_rate",
    "avg_latency_ms": "avg_latency_ms",
    "max_latency_ms": "max_latency_ms",
    "p95_latency_ms": "p95_latency_ms",
}


def top_endpoints_from_raw_sql(
    *,
    filters: AnalyticsFilters,
    error_from: int = 500,
    limit: int = 20,
    sort_by: str = "hits",
    direction: Literal["asc", "desc"] = "desc",
    include_p95: bool = False,
) -> Tuple[str, List[object]]:
    """
    Top endpoints from raw table (fallback).
    Can optionally include p95 in the same query (heavier).
    """
    where_sql, params = build_where_clause(filters, kind="raw", time_column="time")
    dir_sql = "ASC" if direction.lower() == "asc" else "DESC"

    p95_select = ""
    if include_p95:
        p95_select = """,
        (percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms))::double precision AS p95_latency_ms
        """

    sort_col = _RAW_SORT_ALLOWLIST.get(sort_by, "hits")

    sql = f"""
    SELECT
        service,
        endpoint,
        COUNT(*)::bigint AS hits,
        COUNT(*) FILTER (WHERE status_code >= %s)::bigint AS errors,
        CASE
            WHEN COUNT(*) > 0
            THEN (COUNT(*) FILTER (WHERE status_code >= %s)::double precision / COUNT(*)::double precision)
            ELSE 0::double precision
        END AS error_rate,
        AVG(latency_ms)::double precision AS avg_latency_ms,
        MAX(latency_ms)::integer AS max_latency_ms
        {p95_select}
    FROM {RAW_TABLE}
    {where_sql}
    GROUP BY service, endpoint
    ORDER BY {sort_col} {dir_sql}, service ASC, endpoint ASC
    LIMIT %s
    """
    params2 = [error_from, error_from] + params + [limit]
    return sql.strip(), params2
