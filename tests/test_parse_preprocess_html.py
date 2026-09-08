import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.parse_preprocess_html import parse_preprocess_directory
from scripts.work_calendar import WorkCalendar


HTML = """
<html><body><table>
<thead><tr><td>日期</td><td>值班员</td><td>复核员</td></tr></thead>
<tbody>{rows}</tbody></table></body></html>
"""


class PreprocessHtmlTests(unittest.TestCase):
    def setUp(self):
        self.calendar = WorkCalendar(
            year=2026,
            holidays=frozenset({date(2026, 8, 15)}),
            adjusted_workdays=frozenset({date(2026, 8, 22)}),
            source="test",
        )

    def test_merges_pages_dedupes_and_keeps_only_normal_weekends(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "page1.html").write_text(
                HTML.format(rows="<tr><td>2026-08-23</td><td>韩胜</td><td>甲</td></tr>"),
                encoding="utf-8",
            )
            nested = root / "page2_files"
            nested.mkdir()
            (nested / "in(1).html").write_text(
                HTML.format(
                    rows=(
                        "<tr><td>2026-08-23</td><td>韩胜</td><td>甲</td></tr>"
                        "<tr><td>2026-08-15</td><td>张子俊</td><td>乙</td></tr>"
                        "<tr><td>2026-08-22</td><td>吴强</td><td>乙</td></tr>"
                        "<tr><td>2026-08-24</td><td>苏燕红</td><td>乙</td></tr>"
                    )
                ),
                encoding="utf-8",
            )
            result = parse_preprocess_directory(root, 2026, 8, self.calendar)
            self.assertEqual(result.counts, {"韩胜": 1})
            self.assertEqual(result.by_date, {date(2026, 8, 23): "韩胜"})

    def test_different_people_same_day_is_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.html").write_text(
                HTML.format(rows="<tr><td>2026-08-23</td><td>韩胜</td><td>甲</td></tr>"),
                encoding="utf-8",
            )
            (root / "b.html").write_text(
                HTML.format(rows="<tr><td>2026-08-23</td><td>张子俊</td><td>甲</td></tr>"),
                encoding="utf-8",
            )
            result = parse_preprocess_directory(root, 2026, 8, self.calendar)
            self.assertEqual(result.counts, {})
            self.assertEqual(result.conflicts[date(2026, 8, 23)], {"韩胜", "张子俊"})


if __name__ == "__main__":
    unittest.main()
