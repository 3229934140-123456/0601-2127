from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List
import uuid


class CargoType(str, Enum):
    GENERAL = "普通货物"
    DANGEROUS = "危险品"
    REFRIGERATED = "冷藏货物"
    BULK = "散装货物"
    CONTAINER = "集装箱"


class VehicleStatus(str, Enum):
    WAITING = "等待中"
    CALLED = "已叫号"
    LOADING = "装卸中"
    DELAYED = "延迟"
    FINISHED = "已完成"
    CANCELLED = "已取消"


class DelayReason(str, Enum):
    LATE_ARRIVAL = "迟到"
    DOCUMENT_ISSUE = "单据问题"
    CARRIER_REQUEST = "承运商要求"
    YARD_ARRANGEMENT = "场站调度"
    EQUIPMENT_FAILURE = "设备故障"
    PRIORITY_INSERT = "优先插队"
    OTHER = "其他"


class OperationType(str, Enum):
    CHECKIN = "车辆签到"
    CALL = "叫号"
    PLATFORM_CHANGE = "调整月台"
    START_LOADING = "开始装卸"
    FINISH_LOADING = "完成装卸"
    MARK_DELAY = "标记延迟"
    CANCEL = "取消排队"
    BATCH_IMPORT = "批量导入"
    EXPORT_REPORT = "导出报表"


@dataclass
class OperationLog:
    operation_type: OperationType
    operator: str
    description: str
    queue_number: Optional[int] = None
    plate_number: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> dict:
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, Enum):
                data[key] = value.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'OperationLog':
        obj = cls.__new__(cls)
        for key, value in data.items():
            if key == 'operation_type' and isinstance(value, str):
                value = OperationType(value)
            setattr(obj, key, value)
        return obj


@dataclass
class Vehicle:
    plate_number: str
    driver_phone: str
    cargo_type: CargoType
    carrier: str
    appointment_time: str
    checkin_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    queue_number: int = 0
    status: VehicleStatus = VehicleStatus.WAITING
    platform: Optional[str] = None
    call_time: Optional[str] = None
    start_time: Optional[str] = None
    finish_time: Optional[str] = None
    delay_reason: Optional[DelayReason] = None
    delay_note: Optional[str] = None
    delay_time: Optional[str] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    dangerous_level: Optional[str] = None
    temperature_required: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, Enum):
                data[key] = value.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Vehicle':
        obj = cls.__new__(cls)
        for key, value in data.items():
            if key == 'cargo_type' and isinstance(value, str):
                value = CargoType(value)
            elif key == 'status' and isinstance(value, str):
                value = VehicleStatus(value)
            elif key == 'delay_reason' and isinstance(value, str) and value:
                value = DelayReason(value)
            setattr(obj, key, value)
        return obj

    def waiting_minutes(self) -> int:
        now = datetime.now()
        checkin = datetime.strptime(self.checkin_time, "%Y-%m-%d %H:%M:%S")
        return int((now - checkin).total_seconds() / 60)

    def stay_minutes(self) -> Optional[int]:
        if not self.finish_time:
            return None
        finish = datetime.strptime(self.finish_time, "%Y-%m-%d %H:%M:%S")
        checkin = datetime.strptime(self.checkin_time, "%Y-%m-%d %H:%M:%S")
        return int((finish - checkin).total_seconds() / 60)

    def is_overtime(self, threshold_minutes: int = 120) -> bool:
        if self.status in [VehicleStatus.FINISHED, VehicleStatus.CANCELLED]:
            return False
        return self.waiting_minutes() > threshold_minutes


@dataclass
class DailyReport:
    date: str
    total_vehicles: int
    waiting_count: int
    loading_count: int
    finished_count: int
    delayed_count: int
    overtime_count: int
    avg_stay_minutes: float
    carrier_stats: List[dict]
    vehicles: List[Vehicle]
