from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from observability.metrics import apm_ingested_requests_total
from observability.models import ApiRequest
from observability.serializers import ApiRequestIngestItemSerializer


@dataclass(frozen=True)
class IngestConfig:
    max_events: int
    max_errors: int
    batch_size: int
    strict: bool


@dataclass(frozen=True)
class IngestResult:
    inserted: int
    rejected: int
    errors: list[dict[str, Any]]

    def as_response_data(self) -> dict[str, Any]:
        return {
            "inserted": self.inserted,
            "rejected": self.rejected,
            "errors": self.errors,
        }


class IngestPayloadTooLarge(Exception):
    def __init__(self, *, received: int, max_events: int):
        self.received = received
        self.max_events = max_events
        super().__init__(f"Too many events: got {received}, max allowed is {max_events}.")

    def as_response_data(self) -> dict[str, Any]:
        return {
            "detail": str(self),
            "max_events": self.max_events,
        }


class StrictIngestValidationError(Exception):
    def __init__(self, result: IngestResult):
        self.result = result
        super().__init__("Strict mode rejected the ingest payload.")

    def as_response_data(self) -> dict[str, Any]:
        return {
            "detail": (
                "Strict mode enabled: payload contains invalid items. Nothing was inserted."
            ),
            **self.result.as_response_data(),
        }


def parse_ingest_payload(data: Any) -> list[Any]:
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


def ingest_api_requests(data: Any, *, config: IngestConfig) -> IngestResult:
    events = parse_ingest_payload(data)

    if len(events) > config.max_events:
        raise IngestPayloadTooLarge(received=len(events), max_events=config.max_events)

    validated_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    invalid_found = False

    for idx, item in enumerate(events):
        if not isinstance(item, dict):
            invalid_found = True
            if len(errors) < config.max_errors:
                errors.append(
                    {
                        "index": idx,
                        "errors": {"non_field_errors": ["Each event must be a JSON object/dict."]},
                    }
                )
            continue

        serializer = ApiRequestIngestItemSerializer(data=item)
        if serializer.is_valid():
            validated_rows.append(serializer.validated_data)
        else:
            invalid_found = True
            if len(errors) < config.max_errors:
                errors.append({"index": idx, "errors": serializer.errors})

    if config.strict and invalid_found:
        raise StrictIngestValidationError(
            IngestResult(inserted=0, rejected=len(events), errors=errors)
        )

    instances: list[ApiRequest] = [ApiRequest(**row) for row in validated_rows]

    inserted = 0
    if instances:
        with transaction.atomic():
            ApiRequest.objects.bulk_create(instances, batch_size=config.batch_size)
        inserted = len(instances)
        _record_inserted_requests(instances)

    return IngestResult(
        inserted=inserted,
        rejected=len(events) - inserted,
        errors=errors,
    )


def _record_inserted_requests(instances: list[ApiRequest]) -> None:
    inserted_by_label = Counter(
        (
            instance.service,
            f"{instance.status_code // 100}xx",
        )
        for instance in instances
    )
    for (service, status_class), count in inserted_by_label.items():
        apm_ingested_requests_total.labels(
            service=service,
            status_class=status_class,
        ).inc(count)
