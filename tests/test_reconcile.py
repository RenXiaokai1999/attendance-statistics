import unittest
from dataclasses import fields
from datetime import date, datetime

from scripts.models import ApprovalStatus, AttendanceRecord, RecordType
from scripts.reconcile import reconcile_records


def record(kind, *, day=date(2026, 8, 3), approved=True, full=True, version=None, confidence=1.0):
    return AttendanceRecord(
        name="张子俊",
        day=day,
        record_type=kind,
        source="test",
        approval=ApprovalStatus.APPROVED if approved else ApprovalStatus.PENDING,
        full_day=full,
        version_time=version,
        confidence=confidence,
    )


class ReconcileTests(unittest.TestCase):
    def test_attendance_record_has_vehicle_application_marker(self):
        self.assertIn("is_vehicle_application", {field.name for field in fields(AttendanceRecord)})

    def test_same_person_day_and_type_is_deduplicated(self):
        result = reconcile_records([
            record(RecordType.COMP_LEAVE),
            record(RecordType.COMP_LEAVE),
        ])
        self.assertEqual(result.counts[RecordType.COMP_LEAVE], {"张子俊": 1})

    def test_latest_cancellation_removes_record(self):
        result = reconcile_records([
            record(RecordType.COMP_LEAVE, version=datetime(2026, 7, 1, 9)),
            record(RecordType.CANCELLED, version=datetime(2026, 7, 2, 9)),
        ])
        self.assertEqual(result.counts[RecordType.COMP_LEAVE], {})

    def test_vehicle_application_counts_without_approval(self):
        for approval in (
            ApprovalStatus.PENDING,
            ApprovalStatus.REJECTED,
            ApprovalStatus.UNKNOWN,
        ):
            with self.subTest(approval=approval):
                item = AttendanceRecord(
                    name="张子俊",
                    day=date(2026, 8, 3),
                    record_type=RecordType.OFFICIAL_OUT,
                    source="vehicle.png",
                    approval=approval,
                    is_vehicle_application=True,
                )
                result = reconcile_records([item])
                self.assertEqual(
                    result.counts[RecordType.OFFICIAL_OUT],
                    {"张子俊": 1},
                )

    def test_latest_cancellation_does_not_remove_vehicle_application(self):
        vehicle = AttendanceRecord(
            name="张子俊",
            day=date(2026, 8, 3),
            record_type=RecordType.OFFICIAL_OUT,
            source="vehicle.png",
            approval=ApprovalStatus.UNKNOWN,
            version_time=datetime(2026, 7, 1, 9),
            is_vehicle_application=True,
        )
        cancelled = record(
            RecordType.CANCELLED,
            version=datetime(2026, 7, 2, 9),
        )
        result = reconcile_records([vehicle, cancelled])
        self.assertEqual(
            result.counts[RecordType.OFFICIAL_OUT],
            {"张子俊": 1},
        )

    def test_vehicle_application_is_kept_when_another_status_conflicts(self):
        vehicle = AttendanceRecord(
            name="张子俊",
            day=date(2026, 8, 3),
            record_type=RecordType.OFFICIAL_OUT,
            source="vehicle.png",
            approval=ApprovalStatus.UNKNOWN,
            is_vehicle_application=True,
        )
        result = reconcile_records([vehicle, record(RecordType.LEAVE)])
        key = ("张子俊", date(2026, 8, 3))
        self.assertEqual(
            result.counts[RecordType.OFFICIAL_OUT],
            {"张子俊": 1},
        )
        self.assertEqual(result.counts[RecordType.LEAVE], {"张子俊": 1})
        self.assertIs(result.effective_records[key], vehicle)
        self.assertIn(key, result.conflicts)

    def test_unapproved_partial_and_low_confidence_are_not_counted(self):
        result = reconcile_records([
            record(RecordType.LEAVE, approved=False),
            record(RecordType.LEAVE, day=date(2026, 8, 4), full=False),
            record(RecordType.LEAVE, day=date(2026, 8, 5), confidence=0.5),
        ])
        self.assertEqual(result.counts[RecordType.LEAVE], {})
        self.assertEqual(len(result.pending_review), 3)

    def test_multiple_statuses_same_day_are_conflict(self):
        result = reconcile_records([
            record(RecordType.LEAVE),
            record(RecordType.OFFICIAL_OUT),
        ])
        self.assertIn(("张子俊", date(2026, 8, 3)), result.conflicts)
        self.assertEqual(result.counts[RecordType.LEAVE], {})
        self.assertEqual(result.counts[RecordType.OFFICIAL_OUT], {})

    def test_punch_overlap_is_warned_but_status_remains_counted(self):
        result = reconcile_records(
            [record(RecordType.OFFICIAL_OUT)],
            punched_dates={"张子俊": {date(2026, 8, 3)}},
        )
        self.assertEqual(result.counts[RecordType.OFFICIAL_OUT], {"张子俊": 1})
        self.assertEqual(result.punch_overlaps, {("张子俊", date(2026, 8, 3))})

    def test_effective_records_keep_the_selected_detail_record(self):
        item = AttendanceRecord(
            name="张子俊", day=date(2026, 8, 6),
            record_type=RecordType.OFFICIAL_OUT, source="trip.png",
            approval=ApprovalStatus.APPROVED, reason="省预警验收",
        )
        result = reconcile_records([item])
        self.assertIs(result.effective_records[("张子俊", date(2026, 8, 6))], item)


if __name__ == "__main__":
    unittest.main()
