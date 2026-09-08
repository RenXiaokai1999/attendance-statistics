import unittest
from datetime import date, datetime

from scripts.models import ApprovalStatus, AttendanceRecord, RecordType
from scripts.normalize import is_in_month, normalize_name


class NormalizeTests(unittest.TestCase):
    def test_name_removes_spacing_fullwidth_and_invisible_characters(self):
        self.assertEqual(normalize_name("  张\u200b　子 俊\ufeff "), "张子俊")
        self.assertEqual(normalize_name("ＡＢＣ"), "ABC")

    def test_month_boundary(self):
        self.assertFalse(is_in_month(date(2026, 7, 31), 2026, 8))
        self.assertTrue(is_in_month(date(2026, 8, 1), 2026, 8))
        self.assertTrue(is_in_month(date(2026, 8, 31), 2026, 8))
        self.assertFalse(is_in_month(date(2026, 9, 1), 2026, 8))

    def test_record_validates_confidence(self):
        record = AttendanceRecord(
            name="张子俊",
            day=date(2026, 8, 31),
            record_type=RecordType.COMP_LEAVE,
            source="image.png",
            approval=ApprovalStatus.APPROVED,
            full_day=True,
            version_time=datetime(2026, 8, 1, 9, 0),
            confidence=0.95,
        )
        self.assertEqual(record.name, "张子俊")
        with self.assertRaises(ValueError):
            AttendanceRecord(
                name="张子俊",
                day=date(2026, 8, 31),
                record_type=RecordType.LEAVE,
                source="image.png",
                approval=ApprovalStatus.PENDING,
                full_day=True,
                confidence=1.1,
            )


if __name__ == "__main__":
    unittest.main()
