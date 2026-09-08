import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from scripts.config import MonthContext
from scripts.models import ApprovalStatus, AttendanceRecord, RecordType
from scripts.reconcile import ReconcileResult, reconcile_records
import scripts.run_attendance as run_attendance_module
from scripts.run_attendance import (
    PipelinePreflightError, build_official_out_details, build_summaries,
    describe_pending_review, find_missing_leveling_dates,
    load_reviewed_records, preflight,
)


class PipelineTests(unittest.TestCase):
    def test_review_file_loads_unresolved_vehicle_applications(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.json"
            path.write_text(
                '{"groups":[],"unresolved_vehicle_applications":['
                '{"source":"opinion.jpg","note":"缺少用车日期和使用人"}]}',
                encoding="utf-8",
            )
            self.assertEqual(
                getattr(run_attendance_module, "load_unresolved_vehicle_applications", lambda _path: [])(path),
                [{"source": "opinion.jpg", "note": "缺少用车日期和使用人"}],
            )

    def test_review_file_can_group_multiple_days_for_one_person(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.json"
            path.write_text(
                '{"groups":[{"name":"韩胜","days":["2026-08-03","2026-08-04"],'
                '"record_type":"comp_leave","source":"sample.jpg","approval":"approved"}]}',
                encoding="utf-8",
            )
            records = load_reviewed_records(path)
            self.assertEqual([item.day for item in records], [date(2026, 8, 3), date(2026, 8, 4)])

    def test_review_file_loads_official_out_detail_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.json"
            path.write_text(
                '{"groups":[{"name":"梁大勇","days":["2026-08-06"],'
                '"record_type":"official_out","source":"trip.png",'
                '"approval":"approved","official_out_category":"因公外出办事",'
                '"reason":"设备巡检","location":"阳高","approver":"张主任",'
                '"registrant":"梁大勇","companions":["白伟利"],"event_id":"E1",'
                '"event_start":"2026-08-06","event_end":"2026-08-07"}]}',
                encoding="utf-8",
            )
            item = load_reviewed_records(path)[0]
            self.assertEqual(item.reason, "设备巡检")
            self.assertEqual(item.location, "阳高")
            self.assertEqual(item.companions, ("白伟利",))
            self.assertEqual(item.event_id, "E1")
            self.assertEqual(item.event_end, date(2026, 8, 7))

    def test_review_file_loads_vehicle_application_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.json"
            path.write_text(
                '{"groups":[{"name":"梁大勇","days":["2026-08-06"],'
                '"record_type":"official_out","source":"vehicle.png",'
                '"approval":"unknown","is_vehicle_application":true}]}',
                encoding="utf-8",
            )
            item = load_reviewed_records(path)[0]
            self.assertTrue(item.is_vehicle_application)

    def test_official_out_range_expands_every_calendar_day_and_clips_month(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed.json"
            path.write_text(
                '{"month":"202608","groups":[{"name":"白伟利",'
                '"record_type":"official_out","source":"leveling.png",'
                '"approval":"approved","event_start":"2026-08-30",'
                '"event_end":"2026-09-02","reason":"水准测量"}]}',
                encoding="utf-8",
            )
            records = load_reviewed_records(path)
            self.assertEqual(
                [item.day for item in records],
                [date(2026, 8, 30), date(2026, 8, 31)],
            )

    def test_builds_one_detail_per_event_with_all_participants(self):
        records = []
        for name in ("梁大勇", "白伟利", "彭丽娟"):
            for day in (date(2026, 8, 6), date(2026, 8, 7)):
                records.append(
                    AttendanceRecord(
                        name=name, day=day, record_type=RecordType.OFFICIAL_OUT,
                        source="trip.png", approval=ApprovalStatus.APPROVED,
                        event_id="E1", registrant="梁大勇", reason="设备巡检",
                        location="阳高", approver="张主任",
                        official_out_category="因公外出办事",
                        event_start=date(2026, 8, 5), event_end=date(2026, 8, 7),
                    )
                )
        result = reconcile_records(records)
        details, warnings = build_official_out_details(result)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0].registrant, "梁大勇")
        self.assertEqual(details[0].companions, ("白伟利", "彭丽娟"))
        self.assertEqual(details[0].days, (date(2026, 8, 6), date(2026, 8, 7)))
        self.assertEqual(details[0].event_start, date(2026, 8, 5))
        self.assertEqual(warnings, [])

    def test_builds_two_details_for_two_vehicle_events_on_same_day(self):
        records = [
            AttendanceRecord(
                name="任晓凯", day=date(2026, 8, 11),
                record_type=RecordType.OFFICIAL_OUT, source=f"{event_id}.png",
                approval=ApprovalStatus.UNKNOWN, event_id=event_id,
                registrant="任晓凯", reason=reason,
                is_vehicle_application=True,
            )
            for event_id, reason in (
                ("vehicle-morning", "上午送验收材料"),
                ("vehicle-afternoon", "下午补送验收材料"),
            )
        ]
        result = reconcile_records(records)
        details, warnings = build_official_out_details(result)
        self.assertEqual(result.counts[RecordType.OFFICIAL_OUT], {"任晓凯": 1})
        self.assertCountEqual(
            [item.reason for item in details],
            ["下午补送验收材料", "上午送验收材料"],
        )
        self.assertEqual(warnings, [])

    def test_pending_review_report_identifies_the_record(self):
        item = AttendanceRecord(
            name="任晓凯", day=date(2026, 8, 14),
            record_type=RecordType.OFFICIAL_OUT, source="training.png",
            approval=ApprovalStatus.UNKNOWN, reason="参加培训",
            note="未显示审批结果",
        )
        self.assertEqual(describe_pending_review([item]), [{
            "name": "任晓凯", "day": "2026-08-14",
            "record_type": "official_out", "source": "training.png",
            "reason": "参加培训", "note": "未显示审批结果",
        }])

    def test_pending_review_report_deduplicates_expanded_event_days(self):
        records = [
            AttendanceRecord(
                name="任晓凯", day=day, record_type=RecordType.OFFICIAL_OUT,
                source="training.png", approval=ApprovalStatus.UNKNOWN,
                event_id="training-1", reason="参加培训", note="未显示审批结果",
            )
            for day in (date(2026, 8, 14), date(2026, 8, 15))
        ]
        self.assertEqual(len(describe_pending_review(records)), 1)

    def test_leveling_completeness_checks_only_six_fixed_monthly_dates(self):
        records = [
            AttendanceRecord(
                name="韩胜", day=date(2026, 8, day),
                record_type=RecordType.OFFICIAL_OUT, source="leveling.jpg",
                approval=ApprovalStatus.APPROVED, reason="上皇庄水准测量",
            )
            for day in (1, 6, 11, 16, 26)
        ]
        self.assertEqual(
            find_missing_leveling_dates(records, 2026, 8),
            [date(2026, 8, 21)],
        )

    def test_missing_required_source_stops_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = {
                "attendance_root": str(root / "outputs"),
                "manual_source_root": str(root / "manual"),
                "wechat_image_root": str(root / "images"),
                "template_path": str(root / "template.doc"),
            }
            context = MonthContext(2026, 8, settings)
            with self.assertRaises(PipelinePreflightError):
                preflight(context, root / "calendars")
            self.assertFalse(context.output_dir.exists())

    def test_builds_six_word_statistics_and_keeps_zero_values(self):
        reconciliation = ReconcileResult(
            counts={
                RecordType.COMP_LEAVE: {"张子俊": 2},
                RecordType.LEAVE: {"韩胜": 1},
                RecordType.OFFICIAL_OUT: {"张子俊": 3},
            },
            by_person_date={}, conflicts={}, pending_review=[], punch_overlaps=set(),
        )
        summaries = build_summaries(
            attendance={"张子俊": 10, "新人员": 1},
            all_day=Counter({"韩胜": 2}),
            day_duty=Counter({"张子俊": 1}),
            reconciliation=reconciliation,
        )
        self.assertEqual(summaries["张子俊"].attendance, 10)
        self.assertEqual(summaries["张子俊"].official_out, 3)
        self.assertEqual(summaries["张子俊"].comp_leave, 2)
        self.assertEqual(summaries["韩胜"].leave, 1)
        self.assertEqual(summaries["新人员"].all_day_duty, 0)


if __name__ == "__main__":
    unittest.main()
