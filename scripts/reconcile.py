from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from scripts.models import ApprovalStatus, AttendanceRecord, RecordType
from scripts.normalize import normalize_name


COUNTED_TYPES = (
    RecordType.COMP_LEAVE,
    RecordType.LEAVE,
    RecordType.OFFICIAL_OUT,
)


@dataclass(frozen=True)
class ReconcileResult:
    counts: dict[RecordType, dict[str, int]]
    by_person_date: dict[tuple[str, date], RecordType]
    conflicts: dict[tuple[str, date], set[RecordType]]
    pending_review: list[AttendanceRecord]
    punch_overlaps: set[tuple[str, date]]
    effective_records: dict[tuple[str, date], AttendanceRecord] = field(default_factory=dict)
    effective_event_records: tuple[AttendanceRecord, ...] = ()


def _version(record: AttendanceRecord) -> datetime:
    return record.version_time or datetime.min


def reconcile_records(
    records: list[AttendanceRecord],
    punched_dates: dict[str, set[date]] | None = None,
    minimum_confidence: float = 0.8,
) -> ReconcileResult:
    grouped: dict[tuple[str, date], list[AttendanceRecord]] = defaultdict(list)
    for item in records:
        grouped[(normalize_name(item.name), item.day)].append(item)

    by_person_date: dict[tuple[str, date], RecordType] = {}
    effective_records: dict[tuple[str, date], AttendanceRecord] = {}
    conflicts: dict[tuple[str, date], set[RecordType]] = {}
    pending_review: list[AttendanceRecord] = []
    effective_event_records: list[AttendanceRecord] = []
    counted_types_by_key: dict[tuple[str, date], set[RecordType]] = {}

    for key, items in grouped.items():
        cancellations = [item for item in items if item.record_type is RecordType.CANCELLED]
        substantive = [item for item in items if item.record_type in COUNTED_TYPES]
        if cancellations and (
            not substantive or max(map(_version, cancellations)) >= max(map(_version, substantive))
        ):
            substantive = [
                item
                for item in substantive
                if item.record_type is RecordType.OFFICIAL_OUT
                and item.is_vehicle_application
            ]
            if not substantive:
                continue

        latest_by_type: dict[RecordType, AttendanceRecord] = {}
        for item in substantive:
            current = latest_by_type.get(item.record_type)
            if current is None or _version(item) >= _version(current):
                latest_by_type[item.record_type] = item

        vehicle_events: dict[str, AttendanceRecord] = {}
        for item in substantive:
            if (
                item.record_type is RecordType.OFFICIAL_OUT
                and item.is_vehicle_application
                and item.full_day
                and item.confidence >= minimum_confidence
            ):
                event_key = item.event_id.strip() or f"source:{item.source}"
                current = vehicle_events.get(event_key)
                if current is None or _version(item) >= _version(current):
                    vehicle_events[event_key] = item
        if vehicle_events:
            latest_by_type[RecordType.OFFICIAL_OUT] = max(
                vehicle_events.values(), key=_version
            )

        eligible: dict[RecordType, AttendanceRecord] = {}
        for kind, item in latest_by_type.items():
            is_vehicle_application = (
                kind is RecordType.OFFICIAL_OUT and item.is_vehicle_application
            )
            if (
                (item.approval is ApprovalStatus.APPROVED or is_vehicle_application)
                and item.full_day
                and item.confidence >= minimum_confidence
            ):
                eligible[kind] = item
            else:
                pending_review.append(item)

        vehicle_application = next(
            (
                item
                for kind, item in eligible.items()
                if kind is RecordType.OFFICIAL_OUT and item.is_vehicle_application
            ),
            None,
        )
        if len(eligible) > 1 and vehicle_application is not None:
            conflicts[key] = set(eligible)
            by_person_date[key] = RecordType.OFFICIAL_OUT
            effective_records[key] = vehicle_application
            effective_event_records.extend(vehicle_events.values())
            counted_types_by_key[key] = set(eligible)
        elif len(eligible) > 1:
            conflicts[key] = set(eligible)
        elif len(eligible) == 1:
            kind, item = next(iter(eligible.items()))
            by_person_date[key] = kind
            effective_records[key] = item
            counted_types_by_key[key] = {kind}
            if kind is RecordType.OFFICIAL_OUT:
                event_items = list(vehicle_events.values())
                selected_key = item.event_id.strip() or f"source:{item.source}"
                if not any(
                    (event.event_id.strip() or f"source:{event.source}") == selected_key
                    for event in event_items
                ):
                    event_items.append(item)
                effective_event_records.extend(event_items)

    counters: dict[RecordType, Counter[str]] = {
        kind: Counter() for kind in COUNTED_TYPES
    }
    for (name, _day), kinds in counted_types_by_key.items():
        for kind in kinds:
            counters[kind][name] += 1

    punched_dates = punched_dates or {}
    punch_overlaps = {
        key
        for key in by_person_date
        if key[1] in punched_dates.get(key[0], set())
    }
    return ReconcileResult(
        counts={kind: dict(counter) for kind, counter in counters.items()},
        by_person_date=by_person_date,
        conflicts=conflicts,
        pending_review=pending_review,
        punch_overlaps=punch_overlaps,
        effective_records=effective_records,
        effective_event_records=tuple(effective_event_records),
    )
