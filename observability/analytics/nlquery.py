# observability/analytics/nlquery.py
"""Natural-language telemetry queries (Phase 13).

Parse a question into a structured query, then run it over ApiRequest analytics.
An LLM is used when configured; otherwise a keyword heuristic handles the common
shapes ("error rate for checkout in the last 6 hours"). Both paths are $0-capable
and the LLM path always falls back to the heuristic on any failure.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

from django.utils import timezone

from observability.models import ApiRequest

_ERROR_STATUS = 500
METRICS = ("error_rate", "latency_p95", "latency_avg", "request_count")


def _percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(int(round((pct / 100.0) * (len(ordered) - 1))), 0)
    return float(ordered[k])


def _known_services(project) -> list[str]:
    qs = ApiRequest.objects.all()
    if project is not None:
        qs = qs.filter(project=project)
    return list(qs.values_list("service", flat=True).distinct()[:200])


def heuristic_parse(question: str, project=None) -> dict:
    q = question.lower()

    if any(w in q for w in ("error", "fail", "5xx", "500")):
        metric = "error_rate"
    elif any(w in q for w in ("p95", "tail latency")):
        metric = "latency_p95"
    elif any(w in q for w in ("latency", "slow", "duration", "response time")):
        metric = "latency_avg"
    elif any(w in q for w in ("count", "requests", "traffic", "volume", "throughput")):
        metric = "request_count"
    else:
        metric = "error_rate"

    window_hours = 1
    m = re.search(r"last\s+(\d+)\s*(hour|hr|day)", q)
    if m:
        window_hours = int(m.group(1)) * (24 if m.group(2) == "day" else 1)
    elif "yesterday" in q or "last day" in q or "24 hour" in q:
        window_hours = 24
    elif "last night" in q or "overnight" in q:
        window_hours = 12
    elif "last week" in q or "7 day" in q:
        window_hours = 168

    service = None
    for name in _known_services(project):
        if name and re.search(rf"\b{re.escape(name.lower())}\b", q):
            service = name
            break

    endpoint = None
    m = re.search(r"(/[\w/{}\-.:]*)", question)
    if m:
        endpoint = m.group(1)

    return {"metric": metric, "service": service, "endpoint": endpoint, "window_hours": window_hours}


def _llm_parse(question: str, project=None) -> dict | None:
    from observability.ai import llm

    if not llm.is_available():
        return None
    services = _known_services(project)
    system = (
        "Translate the user's telemetry question into a compact JSON object with "
        f"keys: metric (one of {list(METRICS)}), service (one of {services} or null), "
        "endpoint (string or null), window_hours (integer). Output ONLY JSON."
    )
    try:
        raw = llm.complete(question, system=system)
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0) if match else raw)
    except (llm.LLMError, ValueError, AttributeError):
        return None
    if data.get("metric") not in METRICS:
        return None
    data.setdefault("service", None)
    data.setdefault("endpoint", None)
    data["window_hours"] = int(data.get("window_hours") or 1)
    return data


def execute(params: dict, project=None) -> dict:
    until = timezone.now()
    since = until - timedelta(hours=max(int(params.get("window_hours", 1)), 1))
    qs = ApiRequest.objects.filter(time__gte=since, time__lt=until)
    if project is not None:
        qs = qs.filter(project=project)
    if params.get("service"):
        qs = qs.filter(service=params["service"])
    if params.get("endpoint"):
        qs = qs.filter(endpoint=params["endpoint"])

    rows = list(qs.only("status_code", "latency_ms"))
    count = len(rows)
    metric = params.get("metric", "error_rate")
    if metric == "request_count":
        value = float(count)
    elif count == 0:
        value = 0.0
    elif metric == "error_rate":
        value = sum(1 for r in rows if r.status_code >= _ERROR_STATUS) / count
    elif metric == "latency_avg":
        value = sum(r.latency_ms for r in rows) / count
    elif metric == "latency_p95":
        value = _percentile([r.latency_ms for r in rows], 95)
    else:
        value = 0.0

    return {"metric": metric, "value": round(value, 4), "sample_size": count}


def _interpretation(params: dict) -> str:
    scope = params.get("service") or "all services"
    if params.get("endpoint"):
        scope += f" {params['endpoint']}"
    return f"{params['metric']} for {scope} over the last {params['window_hours']}h"


def answer_question(question: str, project=None) -> dict:
    params = _llm_parse(question, project)
    source = "llm"
    if params is None:
        params = heuristic_parse(question, project)
        source = "heuristic"
    result = execute(params, project)
    return {
        "question": question,
        "source": source,
        "params": params,
        "interpretation": _interpretation(params),
        "result": result,
    }
