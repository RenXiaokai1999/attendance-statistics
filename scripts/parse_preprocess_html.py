from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from scripts.normalize import is_in_month, normalize_name
from scripts.work_calendar import WorkCalendar


class _RowParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


@dataclass(frozen=True)
class PreprocessResult:
    counts: dict[str, int]
    by_date: dict[date, str]
    conflicts: dict[date, set[str]]
    warnings: list[str]


def _read_html(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _extract_entries(path: Path) -> list[tuple[date, str]]:
    parser = _RowParser()
    parser.feed(_read_html(path))
    header: tuple[int, int] | None = None
    entries: list[tuple[date, str]] = []
    for row in parser.rows:
        compact = [cell.strip() for cell in row]
        if "日期" in compact and "值班员" in compact:
            header = (compact.index("日期"), compact.index("值班员"))
            continue
        if header is None or max(header) >= len(compact):
            continue
        try:
            day = date.fromisoformat(compact[header[0]])
        except ValueError:
            continue
        entries.append((day, normalize_name(compact[header[1]])))
    return entries


def parse_preprocess_directory(
    directory: Path, year: int, month: int, work_calendar: WorkCalendar
) -> PreprocessResult:
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"缺少数据预处理目录：{directory}")

    names_by_date: dict[date, set[str]] = defaultdict(set)
    warnings: list[str] = []
    for path in sorted(directory.rglob("*.html")):
        for day, name in _extract_entries(path):
            if not is_in_month(day, year, month):
                continue
            if not name:
                warnings.append(f"值班员为空：{path}，{day.isoformat()}")
                continue
            if work_calendar.is_normal_rest_weekend(day):
                names_by_date[day].add(name)

    by_date: dict[date, str] = {}
    conflicts: dict[date, set[str]] = {}
    for day, names in names_by_date.items():
        if len(names) == 1:
            by_date[day] = next(iter(names))
        elif len(names) > 1:
            conflicts[day] = names
    return PreprocessResult(
        counts=dict(Counter(by_date.values())),
        by_date=by_date,
        conflicts=conflicts,
        warnings=warnings,
    )
