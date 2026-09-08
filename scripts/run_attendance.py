from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from scripts.annotate_punch_workbook import annotate_punch_workbook
from scripts.config import MonthContext, PROJECT_ROOT, load_settings
from scripts.models import ApprovalStatus, AttendanceRecord, RecordType
from scripts.parse_all_day_duty import parse_all_day_duty
from scripts.parse_preprocess_html import parse_preprocess_directory
from scripts.parse_punch_records import parse_punch_workbook
from scripts.reconcile import ReconcileResult, reconcile_records
from scripts.validate_outputs import validate_excel_output, validate_word_output
from scripts.work_calendar import WorkCalendar
from scripts.write_attendance_doc import (
    AttendanceSummary, OfficialOutDetail, write_attendance_doc,
)


class PipelinePreflightError(RuntimeError):
    pass


class ReviewRequired(RuntimeError):
    pass


def preflight(context: MonthContext, calendar_dir: Path) -> WorkCalendar:
    missing: list[Path] = []
    for path in (
        Path(context.settings["template_path"]),
        context.all_day_duty_dir,
        context.preprocess_dir,
        Path(calendar_dir) / f"{context.year}.json",
    ):
        if not path.exists():
            missing.append(path)
    if missing:
        joined = "；".join(map(str, missing))
        raise PipelinePreflightError(f"缺少必需输入，已停止：{joined}")
    return WorkCalendar.from_year(context.year, Path(calendar_dir))


def load_reviewed_records(path: Path) -> list[AttendanceRecord]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "groups" in payload:
        items = []
        month_key = str(payload.get("month", ""))
        target_year = int(month_key[:4]) if len(month_key) == 6 and month_key.isdigit() else None
        target_month = int(month_key[4:]) if target_year else None
        for group in payload["groups"]:
            day_values = list(group.get("days", ()))
            if (
                group.get("record_type") == RecordType.OFFICIAL_OUT.value
                and group.get("event_start")
                and group.get("event_end")
            ):
                start = date.fromisoformat(group["event_start"])
                end = date.fromisoformat(group["event_end"])
                if end < start:
                    raise ValueError(f"因公外出结束日期早于开始日期：{group.get('source', '')}")
                day_values = []
                current = start
                while current <= end:
                    if target_year is None or (
                        current.year == target_year and current.month == target_month
                    ):
                        day_values.append(current.isoformat())
                    current += timedelta(days=1)
            for day_value in day_values:
                item = dict(group)
                item.pop("days", None)
                item["day"] = day_value
                items.append(item)
    else:
        items = payload.get("records", payload) if isinstance(payload, dict) else payload
    records: list[AttendanceRecord] = []
    for item in items:
        records.append(
            AttendanceRecord(
                name=item["name"],
                day=date.fromisoformat(item["day"]),
                record_type=RecordType(item["record_type"]),
                source=item["source"],
                approval=ApprovalStatus(item.get("approval", "unknown")),
                full_day=bool(item.get("full_day", True)),
                version_time=(
                    datetime.fromisoformat(item["version_time"])
                    if item.get("version_time")
                    else None
                ),
                confidence=float(item.get("confidence", 1.0)),
                note=item.get("note", ""),
                official_out_category=item.get("official_out_category", ""),
                reason=item.get("reason", ""),
                location=item.get("location", ""),
                approver=item.get("approver", ""),
                registrant=item.get("registrant", ""),
                companions=tuple(item.get("companions", ())),
                event_id=item.get("event_id", ""),
                event_start=(
                    date.fromisoformat(item["event_start"])
                    if item.get("event_start") else None
                ),
                event_end=(
                    date.fromisoformat(item["event_end"])
                    if item.get("event_end") else None
                ),
                is_vehicle_application=bool(item.get("is_vehicle_application", False)),
            )
        )
    return records


def load_unresolved_vehicle_applications(path: Path) -> list[dict[str, str]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    items = payload.get("unresolved_vehicle_applications", [])
    if not isinstance(items, list):
        return []
    return [
        {
            "source": str(item.get("source", "")),
            "note": str(item.get("note", "")),
        }
        for item in items
        if isinstance(item, dict)
    ]


def build_official_out_details(
    reconciliation: ReconcileResult,
) -> tuple[list[OfficialOutDetail], list[str]]:
    grouped: dict[str, list[AttendanceRecord]] = {}
    source_records = (
        reconciliation.effective_event_records
        or tuple(reconciliation.effective_records.values())
    )
    for item in source_records:
        if item.record_type is not RecordType.OFFICIAL_OUT:
            continue
        key = item.event_id.strip() or f"source:{item.source}"
        grouped.setdefault(key, []).append(item)

    details: list[OfficialOutDetail] = []
    warnings: list[str] = []
    for key, items in grouped.items():
        first = items[0]
        reason = next((item.reason.strip() for item in items if item.reason.strip()), "")
        if not reason:
            warnings.append(f"因公外出明细缺少事由：{key}")
            continue
        registrant = next(
            (normalize for item in items if (normalize := item.registrant.strip())),
            items[0].name,
        )
        participants: list[str] = []
        for item in items:
            for name in (item.name, *item.companions):
                if name and name != registrant and name not in participants:
                    participants.append(name)
        days = tuple(sorted({item.day for item in items}))
        event_start = min(
            (item.event_start for item in items if item.event_start), default=days[0]
        )
        event_end = max(
            (item.event_end for item in items if item.event_end), default=days[-1]
        )
        location = next((item.location.strip() for item in items if item.location.strip()), "")
        approver = next((item.approver.strip() for item in items if item.approver.strip()), "")
        category = next(
            (item.official_out_category.strip() for item in items if item.official_out_category.strip()),
            "因公外出",
        )
        remarks = next((item.note.strip() for item in items if item.note.strip()), "")
        details.append(OfficialOutDetail(
            registrant=registrant,
            category=category,
            reason=reason,
            location=location,
            days=days,
            event_start=event_start,
            event_end=event_end,
            approver=approver,
            companions=tuple(participants),
            remarks=remarks,
        ))
    details.sort(key=lambda item: (item.days[0] if item.days else date.max, item.registrant))
    return details, warnings


def describe_pending_review(records: list[AttendanceRecord]) -> list[dict[str, str]]:
    pending_items: list[dict[str, str]] = []
    seen_events: set[str] = set()
    for item in records:
        event_key = item.event_id.strip() or "|".join(
            (item.name, item.record_type.value, item.source, item.reason, item.note)
        )
        if event_key in seen_events:
            continue
        seen_events.add(event_key)
        pending_items.append({
            "name": item.name,
            "day": item.day.isoformat(),
            "record_type": item.record_type.value,
            "source": item.source,
            "reason": item.reason,
            "note": item.note,
        })
    return pending_items


def find_missing_leveling_dates(
    records: list[AttendanceRecord], year: int, month: int
) -> list[date]:
    expected_dates = {date(year, month, day) for day in (1, 6, 11, 16, 21, 26)}
    recorded_dates = {
        item.day
        for item in records
        if item.approval is ApprovalStatus.APPROVED
        and item.record_type is RecordType.OFFICIAL_OUT
        and "水准" in item.reason
    }
    return sorted(expected_dates - recorded_dates)


def build_summaries(
    *,
    attendance: dict[str, int],
    all_day: Counter[str] | dict[str, int],
    day_duty: Counter[str] | dict[str, int],
    reconciliation: ReconcileResult,
) -> dict[str, AttendanceSummary]:
    official = reconciliation.counts[RecordType.OFFICIAL_OUT]
    leave = reconciliation.counts[RecordType.LEAVE]
    comp = reconciliation.counts[RecordType.COMP_LEAVE]
    names = set(attendance) | set(all_day) | set(day_duty) | set(official) | set(leave) | set(comp)
    return {
        name: AttendanceSummary(
            attendance=attendance.get(name, 0),
            official_out=official.get(name, 0),
            leave=leave.get(name, 0),
            all_day_duty=all_day.get(name, 0),
            day_duty=day_duty.get(name, 0),
            comp_leave=comp.get(name, 0),
        )
        for name in names
    }


def run_month(context: MonthContext, reviewed_records_path: Path) -> dict:
    calendar_dir = PROJECT_ROOT / "references" / "workdays"
    work_calendar = preflight(context, calendar_dir)
    punch_path = context.output_dir / context.punch_filename
    if not punch_path.is_file():
        raise PipelinePreflightError(f"缺少整月签卡记录：{punch_path}")
    if not Path(reviewed_records_path).is_file():
        raise ReviewRequired(f"缺少已复核图片记录：{reviewed_records_path}")

    punch = parse_punch_workbook(punch_path, context.year, context.month)
    all_day = parse_all_day_duty(context.all_day_duty_dir, context.year, context.month)
    day_duty = parse_preprocess_directory(
        context.preprocess_dir, context.year, context.month, work_calendar
    )
    reviewed = load_reviewed_records(reviewed_records_path)
    unresolved_vehicle_applications = load_unresolved_vehicle_applications(
        reviewed_records_path
    )
    missing_leveling_dates = find_missing_leveling_dates(
        reviewed, context.year, context.month
    )
    reconciliation = reconcile_records(reviewed, punch.punched_dates)
    official_out_details, detail_warnings = build_official_out_details(reconciliation)
    summaries = build_summaries(
        attendance=punch.attendance_days,
        all_day=all_day.counts,
        day_duty=day_duty.counts,
        reconciliation=reconciliation,
    )

    doc_output = context.output_dir / context.word_output_name
    excel_output = context.output_dir / context.annotated_punch_filename
    if doc_output.exists() or excel_output.exists():
        raise FileExistsError("目标输出已存在；为防止覆盖，请先指定新的验证目录")

    duty_dates = {
        (name, day) for day, name in all_day.by_date.items()
    } | {(name, day) for day, name in day_duty.by_date.items()}
    conflict_dates = set(reconciliation.conflicts)
    conflict_dates |= {
        (name, day) for day, names in all_day.conflicts.items() for name in names
    }
    conflict_dates |= {
        (name, day) for day, names in day_duty.conflicts.items() for name in names
    }

    context.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=context.output_dir) as temp_directory:
        temp_root = Path(temp_directory)
        temp_doc = temp_root / doc_output.name
        temp_excel = temp_root / excel_output.name
        write_attendance_doc(
            Path(context.settings["template_path"]), temp_doc, summaries,
            official_out_details=official_out_details,
        )
        annotate_punch_workbook(
            punch_path,
            temp_excel,
            context.year,
            context.month,
            statuses=reconciliation.by_person_date,
            duty_dates=duty_dates,
            conflicts=conflict_dates,
        )
        validate_word_output(temp_doc, summaries, official_out_details)
        validate_excel_output(temp_excel)
        os.replace(temp_doc, doc_output)
        os.replace(temp_excel, excel_output)

    pending_review_items = describe_pending_review(reconciliation.pending_review)
    report = {
        "month": context.month_key,
        "word_output": str(doc_output),
        "excel_output": str(excel_output),
        "summaries": {name: asdict(summary) for name, summary in summaries.items()},
        "missing_all_day_dates": sorted(day.isoformat() for day in all_day.missing_dates),
        "conflicts": [f"{name} {day.isoformat()}" for name, day in sorted(conflict_dates)],
        "pending_review": len(pending_review_items),
        "pending_review_items": pending_review_items,
        "unresolved_vehicle_applications": unresolved_vehicle_applications,
        "unresolved_vehicle_application_count": len(
            unresolved_vehicle_applications
        ),
        "punch_overlaps": [
            f"{name} {day.isoformat()}" for name, day in sorted(reconciliation.punch_overlaps)
        ],
        "official_out_detail_count": len(official_out_details),
        "official_out_detail_warnings": detail_warnings,
        "missing_leveling_dates": [
            day.isoformat() for day in missing_leveling_dates
        ],
    }
    report_path = context.output_dir / f"{context.month_key}考勤运行报告.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="统计大同台月度考勤")
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    parser.add_argument("--reviewed-records", type=Path, required=True)
    args = parser.parse_args()
    settings = load_settings()
    if args.year and args.month:
        context = MonthContext(args.year, args.month, settings)
    elif args.year or args.month:
        parser.error("--year 与 --month 必须同时提供")
    else:
        context = MonthContext.previous_month(date.today(), settings)
    print(json.dumps(run_month(context, args.reviewed_records), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
