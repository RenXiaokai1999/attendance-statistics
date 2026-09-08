from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class RecordType(str, Enum):
    PUNCH = "punch"
    ALL_DAY_DUTY = "all_day_duty"
    DAY_DUTY = "day_duty"
    COMP_LEAVE = "comp_leave"
    LEAVE = "leave"
    OFFICIAL_OUT = "official_out"
    CANCELLED = "cancelled"


class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AttendanceRecord:
    name: str
    day: date
    record_type: RecordType
    source: str
    approval: ApprovalStatus = ApprovalStatus.UNKNOWN
    full_day: bool = True
    version_time: datetime | None = None
    confidence: float = 1.0
    note: str = ""
    official_out_category: str = ""
    reason: str = ""
    location: str = ""
    approver: str = ""
    registrant: str = ""
    companions: tuple[str, ...] = ()
    event_id: str = ""
    event_start: date | None = None
    event_end: date | None = None
    is_vehicle_application: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("姓名不能为空")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("置信度必须在0到1之间")
