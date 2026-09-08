from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scripts.normalize import normalize_name


@dataclass(frozen=True)
class AttendanceSummary:
    attendance: int = 0
    official_out: int = 0
    leave: int = 0
    all_day_duty: int = 0
    day_duty: int = 0
    comp_leave: int = 0


@dataclass(frozen=True)
class OfficialOutDetail:
    registrant: str
    category: str
    reason: str
    location: str = ""
    days: tuple[date, ...] = ()
    approver: str = ""
    companions: tuple[str, ...] = ()
    remarks: str = ""
    event_start: date | None = None
    event_end: date | None = None


FIELD_LABELS = {
    "attendance": "出勤",
    "official_out": "因公外出",
    "leave": "请假",
    "all_day_duty": "全日班",
    "day_duty": "白班",
    "comp_leave": "补休",
}


def _cell_text(cell) -> str:
    return cell.Range.Text.replace("\r", "").replace("\x07", "").strip()


def _column_map(table) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in range(1, min(table.Rows.Count, 12) + 1):
        for column in range(1, table.Columns.Count + 1):
            try:
                text = _cell_text(table.Cell(row, column))
            except Exception:
                continue
            for field, label in FIELD_LABELS.items():
                if text == label or text.startswith(label + "（"):
                    result.setdefault(field, column)
    missing = set(FIELD_LABELS) - set(result)
    if missing:
        raise ValueError(f"Word模板缺少统计列：{', '.join(sorted(missing))}")
    return result


def _name_rows(table) -> dict[str, int]:
    rows: dict[str, int] = {}
    for row in range(1, table.Rows.Count + 1):
        try:
            name = normalize_name(_cell_text(table.Cell(row, 1)))
        except Exception:
            continue
        if name and name != "姓名":
            rows[name] = row
    return rows


def _month_day(day: date) -> str:
    return f"{day.month}.{day.day}"


def _detail_values(detail: OfficialOutDetail) -> tuple[str, ...]:
    days = tuple(sorted(set(detail.days)))
    start = detail.event_start or (days[0] if days else None)
    end = detail.event_end or (days[-1] if days else None)
    registration_day = _month_day(start) if start else ""
    if not days:
        period = ""
    elif start == end:
        period = f"{_month_day(start)} {len(days)}天"
    else:
        period = f"{_month_day(start)}-{_month_day(end)} {len(days)}天"
    reason_location = detail.reason
    if detail.location:
        reason_location = f"{reason_location}，{detail.location}" if reason_location else detail.location
    notes: list[str] = []
    if detail.companions:
        notes.append("同行 " + " ".join(detail.companions))
    if detail.remarks:
        notes.append(detail.remarks)
    return (
        registration_day,
        detail.registrant,
        detail.category or "因公外出",
        reason_location,
        period,
        detail.approver,
        "；".join(notes),
    )


def _write_official_out_details(table, details: list[OfficialOutDetail]) -> None:
    required_rows = max(1, len(details)) + 1
    while table.Rows.Count < required_rows:
        table.Rows.Add()
    for row in range(2, table.Rows.Count + 1):
        for column in range(1, 8):
            table.Cell(row, column).Range.Text = ""
    for row, detail in enumerate(details, start=2):
        for column, value in enumerate(_detail_values(detail), start=1):
            table.Cell(row, column).Range.Text = value


def _open_word():
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    anchor = word.Documents.Add()
    return pythoncom, word, anchor


def _close_word(pythoncom, word, anchor) -> None:
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


def write_attendance_doc(
    template_path: Path,
    output_path: Path,
    summaries: dict[str, AttendanceSummary],
    *,
    overwrite: bool = False,
    official_out_details: list[OfficialOutDetail] | None = None,
) -> Path:
    template_path = Path(template_path)
    output_path = Path(output_path).resolve()
    if not template_path.is_file():
        raise FileNotFoundError(f"Word模板不存在：{template_path}")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"输出文件已存在：{output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, output_path)

    pythoncom, word, anchor = _open_word()
    document = None
    try:
        document = word.Documents.Open(
            str(output_path), ReadOnly=False, AddToRecentFiles=False
        )
        table = document.Tables(1)
        columns = _column_map(table)
        name_rows = _name_rows(table)
        for raw_name, summary in summaries.items():
            name = normalize_name(raw_name)
            row = name_rows.get(name)
            if row is None:
                table.Rows.Add()
                row = table.Rows.Count
                table.Cell(row, 1).Range.Text = name
                name_rows[name] = row
            for field, column in columns.items():
                value = getattr(summary, field)
                table.Cell(row, column).Range.Text = str(value) if value else ""
        if document.Tables.Count < 2:
            raise ValueError("Word模板缺少因公外出、请（休）假和缺勤情况登记表")
        _write_official_out_details(document.Tables(2), official_out_details or [])
        document.Save()
        document.Close(SaveChanges=False)
        document = None
    finally:
        if document is not None:
            document.Close(SaveChanges=False)
        _close_word(pythoncom, word, anchor)
    return output_path


def read_attendance_doc(path: Path) -> dict[str, dict[str, str]]:
    pythoncom, word, anchor = _open_word()
    document = None
    try:
        document = word.Documents.Open(
            str(Path(path).resolve()), ReadOnly=True, AddToRecentFiles=False
        )
        table = document.Tables(1)
        columns = _column_map(table)
        result: dict[str, dict[str, str]] = {}
        for name, row in _name_rows(table).items():
            result[name] = {
                FIELD_LABELS[field]: _cell_text(table.Cell(row, column))
                for field, column in columns.items()
            }
        return result
    finally:
        if document is not None:
            document.Close(SaveChanges=False)
        _close_word(pythoncom, word, anchor)


def read_official_out_details(path: Path) -> list[dict[str, str]]:
    pythoncom, word, anchor = _open_word()
    document = None
    try:
        document = word.Documents.Open(
            str(Path(path).resolve()), ReadOnly=True, AddToRecentFiles=False
        )
        if document.Tables.Count < 2:
            raise ValueError("Word输出缺少明细登记表")
        table = document.Tables(2)
        labels = ("登记时间", "登记人", "类别", "事由及地点", "起止时间、天数", "批准人", "备注")
        result: list[dict[str, str]] = []
        for row in range(2, table.Rows.Count + 1):
            values = [_cell_text(table.Cell(row, column)) for column in range(1, 8)]
            if any(values):
                result.append(dict(zip(labels, values)))
        return result
    finally:
        if document is not None:
            document.Close(SaveChanges=False)
        _close_word(pythoncom, word, anchor)
