import json
import unittest
from datetime import date
from pathlib import Path

from scripts.config import MonthContext, load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_previous_month_from_run_date(self):
        context = MonthContext.previous_month(date(2026, 9, 1), load_settings())
        self.assertEqual((context.year, context.month), (2026, 8))

    def test_august_2026_paths_and_names(self):
        settings = load_settings()
        context = MonthContext(2026, 8, settings)
        self.assertEqual(context.month_key, "202608")
        self.assertEqual(context.month_folder_name, "2026年8月")
        self.assertEqual(context.word_output_name, "202608DTZ考勤表.doc")
        self.assertEqual(
            context.punch_filename,
            "签卡记录2026-08-01到2026-08-31.xlsx",
        )
        self.assertEqual(
            context.annotated_punch_filename,
            "签卡记录2026-08-01到2026-08-31_考勤标注.xlsx",
        )
        self.assertEqual(
            str(context.all_day_duty_dir),
            r"E:\山西省地震局工作\大同台\考勤\24h值班和预处理\202608\24h值班",
        )
        self.assertEqual(
            str(context.preprocess_dir),
            r"E:\山西省地震局工作\大同台\考勤\24h值班和预处理\202608\数据预处理\2026\8月",
        )
        self.assertEqual(
            [path.name for path in context.image_month_dirs],
            ["2026-07", "2026-08", "2026-09"],
        )

    def test_settings_file_contains_no_login_secret(self):
        settings_path = PROJECT_ROOT / "config" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        flat = json.dumps(data, ensure_ascii=False).lower()
        self.assertIn("credential_target", data)
        self.assertNotIn("password", flat)
        self.assertNotIn("username", flat)


if __name__ == "__main__":
    unittest.main()
