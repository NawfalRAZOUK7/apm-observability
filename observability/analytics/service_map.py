# observability/analytics/service_map.py
"""Derive a service dependency map from span parent/child edges (Phase 7).

A dependency edge exists when a span's parent belongs to a different service:
``parent.service -> child.service``. We aggregate per-edge call volume, error
rate, and latency, compute per-node health, detect the critical path of the
slowest trace, and compare against the previous equal-length window.

Implemented over the ORM in Python so it runs identically on SQLite (tests/dev)
and PostgreSQL. A recursive-CTE version is the natural optimization at scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from observability.models import Span

_ERROR_HTTP = 500
_UNHEALTHY_ERROR_RATE = 0.05


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(int(round((pct / 100.0) * (len(ordered) - 1))), 0)
    return float(ordered[k])


def _is_error(span: Span) -> bool:
    if span.status_code == Span.StatusCode.ERROR:
        return True
    return span.http_status_code is not None and span.http_status_code >= _ERROR_HTTP


@dataclass
class _EdgeAgg:
    calls: int = 0
    errors: int = 0
    durations: list[int] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "error_rate": round(self.errors / self.calls, 4) if self.calls else 0.0,
            "avg_latency_ms": round(sum(self.durations) / len(self.durations), 2)
            if self.durations
            else 0.0,
            "p95_latency_ms": _percentile(self.durations, 95),
            "unhealthy": bool(self.calls) and (self.errors / self.calls) > _UNHEALTHY_ERROR_RATE,
        }


def _window_spans(since: datetime, until: datetime, project=None):
    qs = Span.objects.filter(time__gte=since, time__lt=until)
    if project is not None:
        qs = qs.filter(project=project)
    return list(qs)


def _edges_for(spans: list[Span]) -> dict[tuple[str, str], _EdgeAgg]:
    by_span_id = {s.span_id: s for s in spans}
    edges: dict[tuple[str, str], _EdgeAgg] = {}
    for child in spans:
        parent = by_span_id.get(child.parent_span_id) if child.parent_span_id else None
        if parent is None or parent.service == child.service:
            continue
        agg = edges.setdefault((parent.service, child.service), _EdgeAgg())
        agg.calls += 1
        agg.errors += 1 if _is_error(child) else 0
        agg.durations.append(child.duration_ms)
    return edges


def _nodes_for(spans: list[Span]) -> dict[str, dict]:
    nodes: dict[str, dict] = {}
    for span in spans:
        node = nodes.setdefault(
            span.service, {"service": span.service, "server_calls": 0, "server_errors": 0}
        )
        if span.kind == Span.Kind.SERVER:
            node["server_calls"] += 1
            node["server_errors"] += 1 if _is_error(span) else 0
    for node in nodes.values():
        calls = node["server_calls"]
        node["error_rate"] = round(node["server_errors"] / calls, 4) if calls else 0.0
        node["unhealthy"] = bool(calls) and node["error_rate"] > _UNHEALTHY_ERROR_RATE
    return nodes


def _critical_path(spans: list[Span]) -> list[dict]:
    """Root-to-leaf chain of the slowest trace, following the slowest child."""
    if not spans:
        return []
    # Slowest trace = trace whose root (no parent, or parent absent) is longest.
    by_id = {s.span_id: s for s in spans}
    children: dict[str, list[Span]] = {}
    roots: list[Span] = []
    for s in spans:
        if s.parent_span_id and s.parent_span_id in by_id:
            children.setdefault(s.parent_span_id, []).append(s)
        else:
            roots.append(s)
    if not roots:
        return []
    root = max(roots, key=lambda s: s.duration_ms)

    path: list[dict] = []
    node = root
    seen: set[str] = set()
    while node is not None and node.span_id not in seen:
        seen.add(node.span_id)
        path.append(
            {
                "service": node.service,
                "span": node.name,
                "duration_ms": node.duration_ms,
                "error": _is_error(node),
            }
        )
        kids = children.get(node.span_id, [])
        node = max(kids, key=lambda s: s.duration_ms) if kids else None
    return path


def build_service_map(since: datetime, until: datetime, project=None) -> dict:
    """Return {nodes, edges, critical_path, comparison} for the window."""
    spans = _window_spans(since, until, project)
    edges = _edges_for(spans)
    nodes = _nodes_for(spans)

    # Previous equal-length window for period-over-period comparison.
    span_len = until - since
    prev_edges = _edges_for(_window_spans(since - span_len, since, project))

    edge_list = []
    for (caller, callee), agg in sorted(edges.items()):
        summary = agg.summary()
        prev = prev_edges.get((caller, callee))
        prev_summary = prev.summary() if prev else None
        summary.update(
            {
                "from": caller,
                "to": callee,
                "error_rate_delta": round(
                    summary["error_rate"] - (prev_summary["error_rate"] if prev_summary else 0.0),
                    4,
                ),
                "avg_latency_delta_ms": round(
                    summary["avg_latency_ms"]
                    - (prev_summary["avg_latency_ms"] if prev_summary else 0.0),
                    2,
                ),
            }
        )
        edge_list.append(summary)

    return {
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "nodes": sorted(nodes.values(), key=lambda n: n["service"]),
        "edges": edge_list,
        "critical_path": _critical_path(spans),
        "unhealthy_services": [n["service"] for n in nodes.values() if n["unhealthy"]],
    }
