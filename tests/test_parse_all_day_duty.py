import unittest
from datetime import date

from scripts.parse_all_day_duty import DutyEntry, entry_from_text, merge_duty_entries


class AllDayDutyTests(unittest.TestCase):
    def test_compact_date_can_be_read_from_nested_source_filename(self):
        entry = entry_from_text(
            "地震台网异常零报告\r填报人：高龙飞",
            r"2026\8月\大同站异常零报告-20260801.doc",
        )
        self.assertEqual(entry.day, date(2026, 8, 1))
        self.assertEqual(entry.name, "高龙飞")

    def test_merges_same_person_and_reports_missing_days(self):
        entries = [
            DutyEntry(date(2026, 8, 1), "高龙飞", "a.doc"),
            DutyEntry(date(2026, 8, 1), "高龙飞", "copy.doc"),
            DutyEntry(date(2026, 8, 3), "韩胜", "c.doc"),
        ]
        result = merge_duty_entries(entries, 2026, 8)
        self.assertEqual(result.counts, {"高龙飞": 1, "韩胜": 1})
        self.assertIn(date(2026, 8, 2), result.missing_dates)
        self.assertEqual(result.conflicts, {})

    def test_different_people_on_same_day_conflict_and_count_nobody(self):
        entries = [
            DutyEntry(date(2026, 8, 15), "韩胜", "a.doc"),
            DutyEntry(date(2026, 8, 15), "张子俊", "b.doc"),
        ]
        result = merge_duty_entries(entries, 2026, 8)
        self.assertEqual(result.counts, {})
        self.assertEqual(result.conflicts[date(2026, 8, 15)], {"韩胜", "张子俊"})

    def test_blank_name_is_warning_and_not_counted(self):
        result = merge_duty_entries(
            [DutyEntry(date(2026, 8, 2), "", "blank.doc")], 2026, 8
        )
        self.assertEqual(result.counts, {})
        self.assertIn("blank.doc", result.warnings[0])


if __name__ == "__main__":
    unittest.main()
