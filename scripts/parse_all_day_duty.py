from __future__ import annotations

import calendar
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scripts.normalize import is_in_month, normalize_name


DATE_PATTERNS = (
    re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    re.compile(r"(20\d{2})[-._](\d{1,2})[-._](\d{1,2})"),
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"),
)
REPORTER_PATTERN = re.compile(r"填报人\s*[:：]?\s*([\u4e00-\u9fff]{2,4})")


@dataclass(frozen=True)
class DutyEntry:
    day: date
    name: str
    source: str


@dataclass(frozen=True)
class DutyParseResult:
    counts: dict[str, int]
    by_date: dict[date, str]
    missing_dates: set[date]
    conflicts: dict[date, set[str]]
    warnings: list[str]


def _parse_date(text: str) -> date | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return date(*map(int, match.groups()))
            except ValueError:
                return None
    return None


def entry_from_text(text: str, source: str) -> DutyEntry:
    day = _parse_date(text) or _parse_date(source)
    if day is None:
        raise ValueError("未识别报告日期")
    match = REPORTER_PATTERN.search(text.replace("\r", " ").replace("\x07", " "))
    name = normalize_name(match.group(1)) if match else ""
    return DutyEntry(day=day, name=name, source=source)


def merge_duty_entries(
    entries: list[DutyEntry], year: int, month: int, warnings: list[str] | None = None
) -> DutyParseResult:
    warnings = list(warnings or [])
    names_by_date: dict[date, set[str]] = defaultdict(set)
    seen_dates: set[date] = set()
    for entry in entries:
        if not is_in_month(entry.day, year, month):
            warnings.append(f"忽略非目标月报告：{entry.source}")
            continue
        seen_dates.add(entry.day)
        if not entry.name:
            warnings.append(f"填报人为空：{entry.source}")
            continue
        names_by_date[entry.day].add(normalize_name(entry.name))

    by_date: dict[date, str] = {}
    conflicts: dict[date, set[str]] = {}
    for day, names in names_by_date.items():
        if len(names) == 1:
            by_date[day] = next(iter(names))
        elif len(names) > 1:
            conflicts[day] = names

    counts = dict(Counter(by_date.values()))
    all_days = {
        date(year, month, number)
        for number in range(1, calendar.monthrange(year, month)[1] + 1)
    }
    return DutyParseResult(
        counts=counts,
        by_date=by_date,
        missing_dates=all_days - seen_dates,
        conflicts=conflicts,
        warnings=warnings,
    )


def parse_all_day_duty(directory: Path, year: int, month: int) -> DutyParseResult:
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"缺少24h值班目录：{directory}")

    import pythoncom
    import win32com.client

    entries: list[DutyEntry] = []
    warnings: list[str] = []
    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    anchor = word.Documents.Add()
    try:
        for path in sorted(directory.rglob("*.doc")):
            if path.name.startswith("~$"):
                continue
            document = None
            try:
                document = word.Documents.Open(str(path), ReadOnly=True, AddToRecentFiles=False)
                entries.append(entry_from_text(document.Content.Text, str(path)))
            except Exception:
                warnings.append(f"无法读取或识别：{path}")
            finally:
                if document is not None:
                    document.Close(SaveChanges=False)
    finally:
        try:
            word.Quit(SaveChanges=False)
        except Exception:
            try:
                anchor.Close(SaveChanges=False)
            except Exception:
                pass
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
    return merge_duty_entries(entries, year, month, warnings)
