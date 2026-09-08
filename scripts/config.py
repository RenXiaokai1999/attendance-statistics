from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.json"


def load_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = path or DEFAULT_SETTINGS_PATH
    with settings_path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


@dataclass(frozen=True)
class MonthContext:
    year: int
    month: int
    settings: dict[str, Any]

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError("月份必须在1到12之间")

    @classmethod
    def previous_month(
        cls, run_date: date, settings: dict[str, Any] | None = None
    ) -> "MonthContext":
        year = run_date.year if run_date.month > 1 else run_date.year - 1
        month = run_date.month - 1 if run_date.month > 1 else 12
        return cls(year, month, settings or load_settings())

    @property
    def month_key(self) -> str:
        return f"{self.year:04d}{self.month:02d}"

    @property
    def month_folder_name(self) -> str:
        return f"{self.year}年{self.month}月"

    @property
    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def last_day(self) -> date:
        return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])

    @property
    def output_dir(self) -> Path:
        return Path(self.settings["attendance_root"]) / self.month_folder_name

    @property
    def word_output_name(self) -> str:
        return f"{self.month_key}DTZ考勤表.doc"

    @property
    def punch_filename(self) -> str:
        return f"签卡记录{self.first_day:%Y-%m-%d}到{self.last_day:%Y-%m-%d}.xlsx"

    @property
    def annotated_punch_filename(self) -> str:
        return self.punch_filename.removesuffix(".xlsx") + "_考勤标注.xlsx"

    @property
    def manual_source_dir(self) -> Path:
        return Path(self.settings["manual_source_root"]) / self.month_key

    @property
    def all_day_duty_dir(self) -> Path:
        return self.manual_source_dir / "24h值班"

    @property
    def preprocess_dir(self) -> Path:
        return (
            self.manual_source_dir
            / "数据预处理"
            / str(self.year)
            / f"{self.month}月"
        )

    @property
    def image_month_dirs(self) -> tuple[Path, ...]:
        previous = MonthContext.previous_month(self.first_day, self.settings)
        following = MonthContext(
            self.year + int(self.month == 12),
            1 if self.month == 12 else self.month + 1,
            self.settings,
        )
        image_root = Path(self.settings["wechat_image_root"])
        return (
            image_root / f"{previous.year:04d}-{previous.month:02d}",
            image_root / f"{self.year:04d}-{self.month:02d}",
            image_root / f"{following.year:04d}-{following.month:02d}",
        )
