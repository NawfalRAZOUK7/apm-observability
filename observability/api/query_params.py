from __future__ import annotations

from datetime import UTC, datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import ValidationError


def get_int_query_param(
    request,
    name: str,
    default: int,
    *,
    min_value: int,
    max_value: int | None = None,
) -> int:
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        value = default
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError({name: "Must be an integer."}) from exc

    if value < min_value:
        raise ValidationError({name: f"Must be >= {min_value}."})
    if max_value is not None and value > max_value:
        raise ValidationError({name: f"Must be <= {max_value}."})
    return value


def get_bool_query_param(request, name: str, default: bool = False) -> bool:
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default

    value = str(raw).strip().lower()
    if value in ("1", "true", "t", "yes", "y", "on"):
        return True
    if value in ("0", "false", "f", "no", "n", "off"):
        return False

    raise ValidationError({name: "Must be a boolean (true/false)."})


def get_datetime_or_date_query_param(request, name: str, *, end_of_day: bool = False):
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return None

    value = str(raw).strip()

    parsed_datetime = parse_datetime(value)
    if parsed_datetime is not None:
        if timezone.is_naive(parsed_datetime):
            parsed_datetime = timezone.make_aware(parsed_datetime, timezone=UTC)
        return parsed_datetime.astimezone(UTC)

    parsed_date = parse_date(value)
    if parsed_date is not None:
        if end_of_day:
            parsed_datetime = datetime.combine(parsed_date, time(23, 59, 59, 999999))
        else:
            parsed_datetime = datetime.combine(parsed_date, time(0, 0, 0))
        parsed_datetime = timezone.make_aware(parsed_datetime, timezone=UTC)
        return parsed_datetime.astimezone(UTC)

    raise ValidationError(
        {name: "Must be an ISO datetime or date (e.g. 2025-12-14T10:00:00Z or 2025-12-14)."}
    )
