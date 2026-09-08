import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.work_calendar import CalendarDataMissing, WorkCalendar


class WorkCalendarTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        data = {
            "year": 2026,
            "source": "test fixture",
            "holidays": ["2026-08-15", "2026-08-16"],
            "adjusted_workdays": ["2026-08-22"],
        }
        (self.root / "2026.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_workday_rules(self):
        calendar = WorkCalendar.from_year(2026, self.root)
        self.assertTrue(calendar.is_workday(date(2026, 8, 3)))
        self.assertFalse(calendar.is_workday(date(2026, 8, 15)))
        self.assertTrue(calendar.is_workday(date(2026, 8, 22)))
        self.assertFalse(calendar.is_workday(date(2026, 8, 23)))

    def test_normal_rest_weekend_excludes_holiday_and_adjusted_workday(self):
        calendar = WorkCalendar.from_year(2026, self.root)
        self.assertFalse(calendar.is_normal_rest_weekend(date(2026, 8, 15)))
        self.assertFalse(calendar.is_normal_rest_weekend(date(2026, 8, 22)))
        self.assertTrue(calendar.is_normal_rest_weekend(date(2026, 8, 23)))

    def test_missing_calendar_stops_run(self):
        with self.assertRaises(CalendarDataMissing):
            WorkCalendar.from_year(2025, self.root)


if __name__ == "__main__":
    unittest.main()
