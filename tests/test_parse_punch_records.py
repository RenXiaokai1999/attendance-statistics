import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from scripts.parse_punch_records import parse_punch_workbook


class PunchRecordTests(unittest.TestCase):
    def test_any_number_of_punches_counts_once_per_day(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "punch.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["考勤序号", "姓名", "工号", "所属部门", "8-1\n六", "8-2\n日", "8-3\n一"])
            sheet.append([1, " 张 子俊 ", "30201", "大同台", "", "07:30\n18:00", "08:31\n17:32\n17:35"])
            sheet.append([2, "韩胜", "30202", "大同台", None, None, "08:20"])
            workbook.save(path)

            result = parse_punch_workbook(path, 2026, 8)

            self.assertEqual(result.attendance_days["张子俊"], 2)
            self.assertEqual(result.attendance_days["韩胜"], 1)
            self.assertEqual(
                result.punched_dates["张子俊"],
                {date(2026, 8, 2), date(2026, 8, 3)},
            )
            self.assertEqual(result.date_columns[date(2026, 8, 1)], 5)
            self.assertEqual(result.name_rows["韩胜"], 3)

    def test_rejects_wrong_month_date_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "punch.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["姓名", "7-31"])
            sheet.append(["张子俊", "08:00"])
            workbook.save(path)
            with self.assertRaises(ValueError):
                parse_punch_workbook(path, 2026, 8)


if __name__ == "__main__":
    unittest.main()
