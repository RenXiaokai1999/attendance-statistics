from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable


class CalendarDataMissing(RuntimeError):
    pass


def _parse_days(values: Iterable[str], year: int) -> frozenset[date]:
    days = frozenset(date.fromisoformat(value) for value in values)
    if any(day.year != year for day in days):
        raise ValueError(f"{year}年度日历包含其他年份日期")
    return days


@dataclass(frozen=True)
class WorkCalendar:
    year: int
    holidays: frozenset[date]
    adjusted_workdays: frozenset[date]
    source: str

    @classmethod
    def from_year(cls, year: int, calendar_dir: Path) -> "WorkCalendar":
        path = Path(calendar_dir) / f"{year}.json"
        if not path.is_file():
            raise CalendarDataMissing(f"缺少{year}年度法定节假日数据：{path}")
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        if data.get("year") != year:
            raise ValueError(f"年度日历文件年份不匹配：{path}")
        return cls(
            year=year,
            holidays=_parse_days(data.get("holidays", []), year),
            adjusted_workdays=_parse_days(data.get("adjusted_workdays", []), year),
            source=str(data.get("source", "")),
        )

    def _check_year(self, day: date) -> None:
        if day.year != self.year:
            raise ValueError(f"日期{day.isoformat()}不属于{self.year}年度日历")

    def is_workday(self, day: date) -> bool:
        self._check_year(day)
        if day in self.adjusted_workdays:
            return True
        if day in self.holidays:
            return False
        return day.weekday() < 5

    def is_normal_rest_weekend(self, day: date) -> bool:
        self._check_year(day)
        return (
            day.weekday() >= 5
            and day not in self.holidays
            and day not in self.adjusted_workdays
        )

    def count_workdays(self, start: date, end: date) -> int:
        if end < start:
            raise ValueError("结束日期不能早于开始日期")
        count = 0
        current = start
        while current <= end:
            count += int(self.is_workday(current))
            current += timedelta(days=1)
        return count

