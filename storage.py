import json
import os
import csv
import re
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple
from collections import defaultdict

from models import (Vehicle, VehicleStatus, CargoType, DelayReason, DailyReport,
                    OperationLog, OperationType, PLATFORM_CARGO_FIT)


class QueueStorage:
    PLATFORM_CAPACITY = {"A1": 3, "A2": 3, "B1": 2, "B2": 2, "C1": 4, "C2": 4}
    CARGO_PRIORITY = {
        CargoType.DANGEROUS: 1,
        CargoType.REFRIGERATED: 2,
        CargoType.CONTAINER: 3,
        CargoType.BULK: 4,
        CargoType.GENERAL: 5
    }

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._ensure_daily_file()

    def _get_today_file(self) -> str:
        today = date.today().strftime("%Y-%m-%d")
        return os.path.join(self.data_dir, f"queue_{today}.json")

    def _ensure_daily_file(self):
        filepath = self._get_today_file()
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({"vehicles": [], "last_queue_number": 0, "logs": []}, f, ensure_ascii=False, indent=2)
        else:
            data = self._read_data()
            if "logs" not in data:
                data["logs"] = []
                self._write_data(data)

    def _read_data(self) -> dict:
        filepath = self._get_today_file()
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_data(self, data: dict):
        filepath = self._get_today_file()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_log(self, log: OperationLog):
        data = self._read_data()
        if "logs" not in data:
            data["logs"] = []
        data["logs"].append(log.to_dict())
        self._write_data(data)

    def get_logs(self, operator: Optional[str] = None, operation_type: Optional[OperationType] = None,
                 queue_number: Optional[int] = None, plate_number: Optional[str] = None,
                 start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[OperationLog]:
        data = self._read_data()
        logs = [OperationLog.from_dict(l) for l in data.get("logs", [])]
        if operator:
            logs = [l for l in logs if l.operator == operator]
        if operation_type:
            logs = [l for l in logs if l.operation_type == operation_type]
        if queue_number:
            logs = [l for l in logs if l.queue_number == queue_number]
        if plate_number:
            logs = [l for l in logs if l.plate_number == plate_number]
        if start_time:
            logs = [l for l in logs if l.timestamp >= start_time]
        if end_time:
            logs = [l for l in logs if l.timestamp <= end_time]
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs

    def get_shift_handover_data(self, start_time: Optional[str] = None, end_time: Optional[str] = None) -> Dict:
        vehicles = self.get_all_vehicles()
        last_status = {}
        data = self._read_data()
        all_logs = [OperationLog.from_dict(l) for l in data.get("logs", [])]
        all_logs.sort(key=lambda x: x.timestamp)

        status_change_ops = {
            OperationType.CHECKIN,       # 签到 → 等待中
            OperationType.CALL,          # 叫号 → 已叫号
            OperationType.START_LOADING, # 开始装卸 → 装卸中
            OperationType.FINISH_LOADING,# 完成装卸 → 已完成
            OperationType.MARK_DELAY,    # 标记延迟 → 延迟
            OperationType.RESUME_QUEUE,  # 恢复排队 → 等待中
            OperationType.CANCEL_QUEUE,  # 取消排队 → 已取消
        }

        filtered_logs = all_logs
        if start_time:
            filtered_logs = [l for l in filtered_logs if l.timestamp >= start_time]
        if end_time:
            filtered_logs = [l for l in filtered_logs if l.timestamp <= end_time]

        for v in vehicles:
            v_logs = [l for l in all_logs
                      if l.queue_number == v.queue_number
                      and l.operation_type in status_change_ops
                      and l.plate_number]
            if v_logs:
                last = v_logs[-1]
                last_status[v.queue_number] = {
                    "queue_number": v.queue_number,
                    "plate_number": v.plate_number,
                    "current_status": v.status.value,
                    "last_status_change": last.operation_type.value,
                    "last_status_change_detail": last.description,
                    "last_status_change_time": last.timestamp,
                    "last_operator": last.operator,
                    "platform": v.platform,
                    "carrier": v.carrier,
                    "cargo_type": v.cargo_type.value
                }

        return {
            "period": {"start": start_time or "当日开始", "end": end_time or "当前"},
            "total_vehicles": len(vehicles),
            "summary": {
                "waiting": len([v for v in vehicles if v.status == VehicleStatus.WAITING]),
                "called": len([v for v in vehicles if v.status == VehicleStatus.CALLED]),
                "loading": len([v for v in vehicles if v.status == VehicleStatus.LOADING]),
                "finished": len([v for v in vehicles if v.status == VehicleStatus.FINISHED]),
                "delayed": len([v for v in vehicles if v.status == VehicleStatus.DELAYED]),
                "cancelled": len([v for v in vehicles if v.status == VehicleStatus.CANCELLED]),
            },
            "operations_in_period": len(filtered_logs),
            "logs": filtered_logs,
            "vehicle_last_status": sorted(last_status.values(), key=lambda x: x["queue_number"])
        }

    def export_shift_log(self, filepath: str, start_time: Optional[str] = None,
                         end_time: Optional[str] = None, operator: str = "系统") -> str:
        handover = self.get_shift_handover_data(start_time, end_time)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(handover, f, ensure_ascii=False, indent=2, default=str)
        log = OperationLog(
            operation_type=OperationType.EXPORT_REPORT,
            operator=operator,
            description=f"导出交接班日志，时间段：{handover['period']['start']} ~ {handover['period']['end']}",
        )
        self.add_log(log)
        return filepath

    def get_next_queue_number(self) -> int:
        data = self._read_data()
        next_num = data.get("last_queue_number", 0) + 1
        data["last_queue_number"] = next_num
        self._write_data(data)
        return next_num

    def add_vehicle(self, vehicle: Vehicle, operator: str = "系统") -> Vehicle:
        data = self._read_data()
        if vehicle.queue_number == 0:
            next_num = data.get("last_queue_number", 0) + 1
            data["last_queue_number"] = next_num
            vehicle.queue_number = next_num
        data["vehicles"].append(vehicle.to_dict())
        self._write_data(data)
        log = OperationLog(
            operation_type=OperationType.CHECKIN,
            operator=operator,
            description=f"签到车辆 {vehicle.plate_number}，货类：{vehicle.cargo_type.value}，承运商：{vehicle.carrier}",
            queue_number=vehicle.queue_number,
            plate_number=vehicle.plate_number
        )
        self.add_log(log)
        return vehicle

    def get_all_vehicles(self) -> List[Vehicle]:
        data = self._read_data()
        return [Vehicle.from_dict(v) for v in data.get("vehicles", [])]

    def get_vehicle_by_id(self, vehicle_id: str) -> Optional[Vehicle]:
        for v in self.get_all_vehicles():
            if v.id == vehicle_id:
                return v
        return None

    def get_vehicle_by_plate(self, plate_number: str) -> Optional[Vehicle]:
        for v in self.get_all_vehicles():
            if v.plate_number == plate_number:
                return v
        return None

    def get_vehicle_by_queue(self, queue_number: int) -> Optional[Vehicle]:
        for v in self.get_all_vehicles():
            if v.queue_number == queue_number:
                return v
        return None

    def update_vehicle(self, vehicle: Vehicle) -> bool:
        data = self._read_data()
        vehicles = data.get("vehicles", [])
        for i, v in enumerate(vehicles):
            if v["id"] == vehicle.id:
                vehicles[i] = vehicle.to_dict()
                self._write_data(data)
                return True
        return False

    def get_waiting_vehicles(self, cargo_type: Optional[CargoType] = None) -> List[Vehicle]:
        vehicles = self.get_all_vehicles()
        waiting = [v for v in vehicles if v.status in [VehicleStatus.WAITING, VehicleStatus.DELAYED]]
        if cargo_type:
            waiting = [v for v in waiting if v.cargo_type == cargo_type]
        waiting.sort(key=lambda x: (x.status != VehicleStatus.DELAYED, x.queue_number))
        return waiting

    def get_dangerous_vehicles(self) -> List[Vehicle]:
        return [v for v in self.get_all_vehicles() if v.cargo_type == CargoType.DANGEROUS]

    def get_refrigerated_vehicles(self) -> List[Vehicle]:
        return [v for v in self.get_all_vehicles() if v.cargo_type == CargoType.REFRIGERATED]

    def get_overtime_vehicles(self, threshold_minutes: int = 120) -> List[Vehicle]:
        return [v for v in self.get_all_vehicles() if v.is_overtime(threshold_minutes)]

    def get_ready_vehicles(self, cargo_type: Optional[CargoType] = None) -> List[Vehicle]:
        vehicles = self.get_all_vehicles()
        ready = [v for v in vehicles if v.status == VehicleStatus.WAITING]
        if cargo_type:
            ready = [v for v in ready if v.cargo_type == cargo_type]
        ready.sort(key=lambda x: x.queue_number)
        return ready

    def call_vehicles(self, count: int = 1, platform: Optional[str] = None, include_delayed: bool = False, operator: str = "系统") -> List[Vehicle]:
        if include_delayed:
            waiting = self.get_waiting_vehicles()
        else:
            waiting = self.get_ready_vehicles()
        called = []
        for v in waiting:
            if len(called) >= count:
                break
            if v.status == VehicleStatus.WAITING or (include_delayed and v.status == VehicleStatus.DELAYED):
                v.status = VehicleStatus.CALLED
                v.call_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if platform:
                    v.platform = platform
                self.update_vehicle(v)
                called.append(v)
        if called:
            queue_nums = ",".join([f"#{v.queue_number}" for v in called])
            platform_info = f"，月台：{platform}" if platform else ""
            log = OperationLog(
                operation_type=OperationType.CALL,
                operator=operator,
                description=f"叫号 {len(called)} 辆：{queue_nums}{platform_info}",
                queue_number=called[0].queue_number
            )
            self.add_log(log)
            for v in called:
                per_log = OperationLog(
                    operation_type=OperationType.CALL,
                    operator=operator,
                    description=f"叫号 #{v.queue_number} {v.plate_number}，月台：{v.platform or '未分配'}",
                    queue_number=v.queue_number,
                    plate_number=v.plate_number
                )
                self.add_log(per_log)
        return called

    def call_specific_vehicles(self, queue_numbers: List[int], platform: Optional[str] = None, operator: str = "系统") -> List[Vehicle]:
        called = []
        for qn in queue_numbers:
            v = self.get_vehicle_by_queue(qn)
            if v and v.status in [VehicleStatus.WAITING, VehicleStatus.DELAYED]:
                v.status = VehicleStatus.CALLED
                v.call_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if platform:
                    v.platform = platform
                self.update_vehicle(v)
                called.append(v)
        if called:
            queue_nums = ",".join([f"#{v.queue_number}" for v in called])
            platform_info = f"，月台：{platform}" if platform else ""
            log = OperationLog(
                operation_type=OperationType.CALL,
                operator=operator,
                description=f"指定叫号：{queue_nums}{platform_info}",
                queue_number=called[0].queue_number
            )
            self.add_log(log)
            for v in called:
                per_log = OperationLog(
                    operation_type=OperationType.CALL,
                    operator=operator,
                    description=f"指定叫号 #{v.queue_number} {v.plate_number}，月台：{platform or '未分配'}",
                    queue_number=v.queue_number,
                    plate_number=v.plate_number
                )
                self.add_log(per_log)
        return called

    def set_platform(self, queue_number: int, platform: str, operator: str = "系统") -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v:
            old_platform = v.platform or "未分配"
            v.platform = platform
            self.update_vehicle(v)
            log = OperationLog(
                operation_type=OperationType.PLATFORM_CHANGE,
                operator=operator,
                description=f"调整 #{queue_number} {v.plate_number} 月台：{old_platform} → {platform}",
                queue_number=queue_number,
                plate_number=v.plate_number
            )
            self.add_log(log)
            return v
        return None

    def mark_delay(self, queue_number: int, reason: DelayReason, note: Optional[str] = None, operator: str = "系统") -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v:
            v.status = VehicleStatus.DELAYED
            v.delay_reason = reason
            v.delay_note = note
            v.delay_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_vehicle(v)
            note_info = f"，备注：{note}" if note else ""
            log = OperationLog(
                operation_type=OperationType.MARK_DELAY,
                operator=operator,
                description=f"标记 #{queue_number} {v.plate_number} 延迟，原因：{reason.value}{note_info}",
                queue_number=queue_number,
                plate_number=v.plate_number
            )
            self.add_log(log)
            return v
        return None

    def resume_queue(self, queue_number: int, operator: str = "系统") -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v and v.status == VehicleStatus.DELAYED:
            old_reason = v.delay_reason.value if v.delay_reason else ""
            v.status = VehicleStatus.WAITING
            v.delay_reason = None
            v.delay_note = None
            v.delay_time = None
            self.update_vehicle(v)
            log = OperationLog(
                operation_type=OperationType.RESUME_QUEUE,
                operator=operator,
                description=f"恢复 #{queue_number} {v.plate_number} 排队（原延迟原因：{old_reason}）",
                queue_number=queue_number,
                plate_number=v.plate_number
            )
            self.add_log(log)
            return v
        return None

    def cancel_queue(self, queue_number: int, operator: str = "系统") -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v and v.status in [VehicleStatus.WAITING, VehicleStatus.DELAYED, VehicleStatus.CALLED]:
            old_status = v.status.value
            v.status = VehicleStatus.CANCELLED
            self.update_vehicle(v)
            log = OperationLog(
                operation_type=OperationType.CANCEL_QUEUE,
                operator=operator,
                description=f"取消 #{queue_number} {v.plate_number} 排队（原状态：{old_status}）",
                queue_number=queue_number,
                plate_number=v.plate_number
            )
            self.add_log(log)
            return v
        return None

    def change_appointment(self, queue_number: int, new_appointment: str, operator: str = "系统") -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v:
            old_appt = v.appointment_time
            v.appointment_time = new_appointment
            self.update_vehicle(v)
            log = OperationLog(
                operation_type=OperationType.CHANGE_APPOINTMENT,
                operator=operator,
                description=f"修改 #{queue_number} {v.plate_number} 预约时段：{old_appt} → {new_appointment}",
                queue_number=queue_number,
                plate_number=v.plate_number
            )
            self.add_log(log)
            return v
        return None

    def start_loading(self, queue_number: int, operator: str = "系统") -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v and v.status == VehicleStatus.CALLED:
            v.status = VehicleStatus.LOADING
            v.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_vehicle(v)
            log = OperationLog(
                operation_type=OperationType.START_LOADING,
                operator=operator,
                description=f"#{queue_number} {v.plate_number} 开始装卸，月台：{v.platform or '未分配'}",
                queue_number=queue_number,
                plate_number=v.plate_number
            )
            self.add_log(log)
            return v
        return None

    def finish_loading(self, queue_number: int, operator: str = "系统") -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v and v.status == VehicleStatus.LOADING:
            v.status = VehicleStatus.FINISHED
            v.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_vehicle(v)
            stay = v.stay_minutes() or 0
            log = OperationLog(
                operation_type=OperationType.FINISH_LOADING,
                operator=operator,
                description=f"#{queue_number} {v.plate_number} 完成装卸，停留时长：{stay}分钟",
                queue_number=queue_number,
                plate_number=v.plate_number
            )
            self.add_log(log)
            return v
        return None

    def get_carrier_stats(self, vehicles: Optional[List[Vehicle]] = None) -> List[dict]:
        if vehicles is None:
            vehicles = self.get_all_vehicles()
        stats = defaultdict(lambda: {"count": 0, "total_stay": 0, "finished": 0, "avg_stay": 0})
        for v in vehicles:
            carrier = v.carrier or "未知"
            stats[carrier]["count"] += 1
            if v.status == VehicleStatus.FINISHED:
                stats[carrier]["finished"] += 1
                stay = v.stay_minutes()
                if stay is not None:
                    stats[carrier]["total_stay"] += stay
        result = []
        for carrier, data in stats.items():
            avg_stay = data["total_stay"] / data["finished"] if data["finished"] > 0 else 0
            result.append({
                "carrier": carrier,
                "total": data["count"],
                "finished": data["finished"],
                "avg_stay_minutes": round(avg_stay, 1),
                "total_stay_minutes": data["total_stay"]
            })
        result.sort(key=lambda x: x["avg_stay_minutes"], reverse=True)
        return result

    def filter_vehicles(self, carrier: Optional[str] = None, cargo_type: Optional[CargoType] = None,
                       platform: Optional[str] = None, status: Optional[VehicleStatus] = None) -> List[Vehicle]:
        vehicles = self.get_all_vehicles()
        if carrier:
            vehicles = [v for v in vehicles if v.carrier == carrier]
        if cargo_type:
            vehicles = [v for v in vehicles if v.cargo_type == cargo_type]
        if platform:
            vehicles = [v for v in vehicles if v.platform == platform]
        if status:
            vehicles = [v for v in vehicles if v.status == status]
        return vehicles

    def _compute_vehicle_summary(self, vehicles: List[Vehicle], threshold: int = 120) -> Dict:
        finished_list = [v for v in vehicles if v.status == VehicleStatus.FINISHED]
        total_stay = sum(v.stay_minutes() or 0 for v in finished_list)
        avg_stay = round(total_stay / len(finished_list), 1) if finished_list else 0
        return {
            "waiting": len([v for v in vehicles if v.status == VehicleStatus.WAITING]),
            "called": len([v for v in vehicles if v.status == VehicleStatus.CALLED]),
            "loading": len([v for v in vehicles if v.status == VehicleStatus.LOADING]),
            "finished": len(finished_list),
            "delayed": len([v for v in vehicles if v.status == VehicleStatus.DELAYED]),
            "cancelled": len([v for v in vehicles if v.status == VehicleStatus.CANCELLED]),
            "overtime": len([v for v in vehicles if v.is_overtime(threshold)]),
            "avg_stay_minutes": avg_stay
        }

    def get_daily_report(self, carrier: Optional[str] = None, cargo_type: Optional[CargoType] = None,
                         platform: Optional[str] = None) -> DailyReport:
        vehicles = self.filter_vehicles(carrier=carrier, cargo_type=cargo_type, platform=platform)
        finished = [v for v in vehicles if v.status == VehicleStatus.FINISHED]
        total_stay = sum(v.stay_minutes() or 0 for v in finished)
        avg_stay = total_stay / len(finished) if finished else 0
        overtime_in_filter = len([v for v in vehicles if v.is_overtime()])
        return DailyReport(
            date=date.today().strftime("%Y-%m-%d"),
            total_vehicles=len(vehicles),
            waiting_count=len([v for v in vehicles if v.status == VehicleStatus.WAITING]),
            loading_count=len([v for v in vehicles if v.status == VehicleStatus.LOADING]),
            finished_count=len(finished),
            delayed_count=len([v for v in vehicles if v.status == VehicleStatus.DELAYED]),
            overtime_count=overtime_in_filter,
            avg_stay_minutes=round(avg_stay, 1),
            carrier_stats=self.get_carrier_stats(vehicles),
            vehicles=vehicles
        )

    def _validate_dangerous_level(self, level: str) -> Optional[str]:
        if not level:
            return "危险品未填写 dangerous_level"
        level = level.strip()
        valid_patterns = [
            r'^[1-9](\.\d)?$',
            r'^[1-9]类$',
            r'^[1-9]\.\d类$',
            r'^[一二三四五六七八九]级$',
            r'^[一二三四五六七八九]类$',
            r'^甲[级类]$',
            r'^乙[级类]$',
            r'^丙[级类]$',
            r'^GB\d+$',
            r'^UN\d+$',
        ]
        for pat in valid_patterns:
            if re.match(pat, level):
                return None
        return f"危险品等级 '{level}' 格式不合规（如：1类/3类/一级/甲级/二级 等）"

    def _validate_temperature(self, temp: str) -> Optional[str]:
        if not temp:
            return "冷藏货未填写 temperature"
        temp = temp.strip()
        valid_patterns = [
            r'^-?\d+(\.\d+)?$',
            r'^-?\d+(\.\d+)?℃$',
            r'^-?\d+(\.\d+)?°C$',
            r'^-?\d+(\.\d+)?度$',
            r'^-?\d+(\.\d+)?\s*[~至\-]\s*-?\d+(\.\d+)?(℃|°C|度)?$',
            r'^冷冻$',
            r'^冷藏$',
            r'^室温$',
            r'^常温$',
            r'^恒温\d+(\.\d+)?(℃|°C)?$',
        ]
        for pat in valid_patterns:
            if re.match(pat, temp):
                return None
        return f"冷藏温度 '{temp}' 格式不合规（如 -18℃、-18°C、2~8度、冷冻 等）"

    def _validate_csv_row(self, row: dict, row_num: int, existing_plates: set) -> Tuple[List[str], Optional[CargoType]]:
        warnings = []
        cargo_type_map = {
            '普通货物': CargoType.GENERAL, '普通': CargoType.GENERAL, 'general': CargoType.GENERAL,
            '危险品': CargoType.DANGEROUS, 'dangerous': CargoType.DANGEROUS,
            '冷藏货物': CargoType.REFRIGERATED, '冷藏': CargoType.REFRIGERATED, 'refrigerated': CargoType.REFRIGERATED,
            '散装货物': CargoType.BULK, '散装': CargoType.BULK, 'bulk': CargoType.BULK,
            '集装箱': CargoType.CONTAINER, 'container': CargoType.CONTAINER
        }

        plate = row.get('plate', '').strip()
        phone = row.get('phone', '').strip()
        cargo_str = row.get('cargo', '').strip()
        carrier = row.get('carrier', '').strip()
        appointment = row.get('appointment', '').strip()
        dangerous_level = row.get('dangerous_level', '').strip() or None
        temperature = row.get('temperature', '').strip() or None

        if not all([plate, phone, cargo_str, carrier, appointment]):
            return [f"第{row_num}行: 缺少必填字段"], None

        if plate in existing_plates:
            return [f"第{row_num}行: 车牌 {plate} 已在排队中，将跳过"], None

        if not re.match(r'^1[3-9]\d{9}$', phone):
            warnings.append(f"第{row_num}行: 电话 {phone} 格式不合规（应为11位手机号）")

        cargo_type = cargo_type_map.get(cargo_str.lower())
        if not cargo_type:
            return [f"第{row_num}行: 无效货类 '{cargo_str}'"], None

        if cargo_type == CargoType.DANGEROUS:
            err = self._validate_dangerous_level(dangerous_level or "")
            if err:
                warnings.append(f"第{row_num}行: {err}")

        if cargo_type == CargoType.REFRIGERATED:
            err = self._validate_temperature(temperature or "")
            if err:
                warnings.append(f"第{row_num}行: {err}")

        try:
            if len(appointment) <= 5 and ':' in appointment:
                appt_check = f"{date.today().strftime('%Y-%m-%d')} {appointment}:00"
            else:
                appt_check = appointment
            datetime.strptime(appt_check, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            warnings.append(f"第{row_num}行: 预约时间 '{appointment}' 格式不合规")

        return warnings, cargo_type

    def preview_csv_import(self, filepath: str) -> Dict:
        existing_plates = {v.plate_number for v in self.get_all_vehicles()
                          if v.status not in [VehicleStatus.FINISHED, VehicleStatus.CANCELLED]}

        valid_rows = []
        warnings = []
        skipped_rows = []
        error_rows = []
        raw_rows = []
        seen_in_csv = set()

        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                required_cols = {'plate', 'phone', 'cargo', 'carrier', 'appointment'}
                if not required_cols.issubset(set(reader.fieldnames or [])):
                    missing = required_cols - set(reader.fieldnames or [])
                    return {"error": f"缺少必要列: {', '.join(missing)}", "valid": 0, "warnings": [], "skipped": 0, "errors": 1}

                for row_num, row in enumerate(reader, start=2):
                    raw_rows.append(row)
                    plate = row.get('plate', '').strip()

                    if plate in seen_in_csv:
                        skipped_rows.append({"row": row_num, "reason": f"第{row_num}行: 车牌 {plate} 在CSV内重复，已跳过", "data": row})
                        warnings.append(f"第{row_num}行: 车牌 {plate} 在CSV内重复，已跳过")
                        continue

                    row_warnings, cargo_type = self._validate_csv_row(row, row_num, existing_plates)

                    if cargo_type is None:
                        if row_warnings:
                            if "已在排队中" in row_warnings[0]:
                                skipped_rows.append({"row": row_num, "reason": row_warnings[0], "data": row})
                                warnings.extend(row_warnings)
                            else:
                                error_rows.append({"row": row_num, "reason": row_warnings[0], "data": row})
                                warnings.extend(row_warnings)
                        continue

                    if any("未填写" in w or "不合规" in w for w in row_warnings):
                        error_rows.append({"row": row_num, "reason": "; ".join(row_warnings), "data": row})
                        warnings.extend(row_warnings)
                        seen_in_csv.add(plate)
                        continue

                    warnings.extend(row_warnings)
                    seen_in_csv.add(plate)
                    phone = row.get('phone', '').strip()
                    carrier = row.get('carrier', '').strip()
                    appointment = row.get('appointment', '').strip()
                    dangerous_level = row.get('dangerous_level', '').strip() or None
                    temperature = row.get('temperature', '').strip() or None

                    valid_rows.append({
                        "row_num": row_num, "plate": plate, "phone": phone,
                        "cargo_type": cargo_type, "carrier": carrier,
                        "appointment": appointment, "dangerous_level": dangerous_level,
                        "temperature": temperature
                    })

        except Exception as e:
            return {"error": f"文件读取失败: {str(e)}", "valid": 0, "warnings": [], "skipped": 0, "errors": 1}

        return {
            "valid": len(valid_rows),
            "skipped": len(skipped_rows),
            "errors": len(error_rows),
            "warnings": warnings,
            "valid_rows": valid_rows,
            "skipped_rows": skipped_rows,
            "error_rows": error_rows
        }

    def execute_csv_import(self, preview_result: Dict, operator: str = "系统") -> Tuple[int, int, int, List[str]]:
        existing_plates = {v.plate_number for v in self.get_all_vehicles()
                          if v.status not in [VehicleStatus.FINISHED, VehicleStatus.CANCELLED]}

        success = 0
        skipped = 0
        errors = 0
        error_details = []

        for row_info in preview_result.get("valid_rows", []):
            try:
                appointment = row_info["appointment"]
                if len(appointment) <= 5 and ':' in appointment:
                    today = date.today().strftime("%Y-%m-%d")
                    appointment = f"{today} {appointment}:00"

                if row_info["plate"] in existing_plates:
                    skipped += 1
                    error_details.append(f"第{row_info['row_num']}行: 车牌 {row_info['plate']} 导入时已在排队中")
                    continue

                vehicle = Vehicle(
                    plate_number=row_info["plate"],
                    driver_phone=row_info["phone"],
                    cargo_type=row_info["cargo_type"],
                    carrier=row_info["carrier"],
                    appointment_time=appointment,
                    dangerous_level=row_info["dangerous_level"],
                    temperature_required=row_info["temperature"]
                )
                self.add_vehicle(vehicle, operator=operator)
                existing_plates.add(row_info["plate"])
                success += 1
            except Exception as e:
                errors += 1
                error_details.append(f"第{row_info['row_num']}行: {str(e)}")

        for err in preview_result.get("skipped_rows", []):
            skipped += 1
            error_details.append(err["reason"])

        for err in preview_result.get("error_rows", []):
            errors += 1
            error_details.append(err["reason"])

        log = OperationLog(
            operation_type=OperationType.BATCH_IMPORT,
            operator=operator,
            description=f"CSV批量导入完成：成功{success}辆，跳过{skipped}辆，错误{errors}辆",
        )
        self.add_log(log)

        return success, skipped, errors, error_details

    def export_failed_rows(self, error_rows: List[dict], filepath: str) -> str:
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['row', 'reason', 'plate', 'phone', 'cargo', 'carrier', 'appointment', 'dangerous_level', 'temperature'])
            writer.writeheader()
            for err in error_rows:
                data = err.get("data", {})
                writer.writerow({
                    'row': err.get('row', ''),
                    'reason': err.get('reason', ''),
                    'plate': data.get('plate', ''),
                    'phone': data.get('phone', ''),
                    'cargo': data.get('cargo', ''),
                    'carrier': data.get('carrier', ''),
                    'appointment': data.get('appointment', ''),
                    'dangerous_level': data.get('dangerous_level', ''),
                    'temperature': data.get('temperature', '')
                })
        return filepath

    def get_dispatch_suggestion(self, count: int = 3) -> Dict:
        ready = self.get_ready_vehicles()
        if not ready:
            return {"suggestions": [], "reason": "没有可调度的车辆", "platform_status": {},
                    "unassigned_reason": None}

        now = datetime.now()

        platform_loading = defaultdict(int)
        for v in self.get_all_vehicles():
            if v.status in [VehicleStatus.LOADING, VehicleStatus.CALLED] and v.platform:
                platform_loading[v.platform] += 1

        platform_available = {}
        for p, cap in self.PLATFORM_CAPACITY.items():
            current = platform_loading.get(p, 0)
            platform_available[p] = {"loading": current, "capacity": cap, "available": cap - current}

        total_available = sum(p["available"] for p in platform_available.values())
        if total_available == 0:
            return {
                "suggestions": [],
                "reason": "所有月台已满，无法叫号",
                "platform_status": platform_available,
                "unassigned_reason": "月台满载"
            }

        def score_vehicle(v: Vehicle) -> Tuple[float, int, int]:
            try:
                appt_time = datetime.strptime(v.appointment_time, "%Y-%m-%d %H:%M:%S")
                minutes_since_appt = max(0, (now - appt_time).total_seconds() / 60)
            except:
                minutes_since_appt = -1

            cargo_priority = self.CARGO_PRIORITY.get(v.cargo_type, 5)
            queue_priority = v.queue_number

            return (-minutes_since_appt, cargo_priority, queue_priority)

        scored = [(score_vehicle(v), v) for v in ready]
        scored.sort(key=lambda x: x[0])

        suggestions = []
        skipped_no_platform = []

        for score, v in scored:
            if len(suggestions) >= count:
                break
            if total_available <= 0:
                skipped_no_platform.append(v)
                continue

            best_platform = None
            best_score = -1
            fallback_platform = None
            fallback_score = -1

            for platform, cap_info in self.PLATFORM_CAPACITY.items():
                if platform_available[platform]["available"] <= 0:
                    continue
                fit_cargos = PLATFORM_CARGO_FIT.get(platform, [])
                if v.cargo_type in fit_cargos:
                    score_val = 100 - platform_available[platform]["loading"]
                    if score_val > best_score:
                        best_score = score_val
                        best_platform = platform
                else:
                    score_val = 10 - platform_available[platform]["loading"]
                    if score_val > fallback_score:
                        fallback_score = score_val
                        fallback_platform = platform

            chosen_platform = best_platform or fallback_platform

            if not chosen_platform:
                skipped_no_platform.append(v)
                continue

            reasons = []
            try:
                appt_time = datetime.strptime(v.appointment_time, "%Y-%m-%d %H:%M:%S")
                if appt_time <= now:
                    overdue = int((now - appt_time).total_seconds() / 60)
                    reasons.append(f"预约{overdue}分钟前已到")
                else:
                    remaining = int((appt_time - now).total_seconds() / 60)
                    reasons.append(f"预约{remaining}分钟后")
            except:
                reasons.append("预约时间格式异常")

            prio = self.CARGO_PRIORITY.get(v.cargo_type, 5)
            reasons.append(f"货类优先级{prio}({v.cargo_type.value})")

            if best_platform:
                fit_cargos = PLATFORM_CARGO_FIT.get(best_platform, [])
                reasons.append(f"月台{chosen_platform}适配{v.cargo_type.value}")
            else:
                reasons.append(f"月台{chosen_platform}非专用(备选)")

            reasons.append(f"已等{v.waiting_minutes()}分钟")
            reasons.append(f"排队号#{v.queue_number}")

            suggestions.append({
                "queue_number": v.queue_number,
                "plate_number": v.plate_number,
                "cargo_type": v.cargo_type.value,
                "carrier": v.carrier,
                "suggested_platform": chosen_platform,
                "platform_match": best_platform is not None,
                "reasons": reasons,
                "waiting_minutes": v.waiting_minutes()
            })
            platform_available[chosen_platform]["available"] -= 1
            platform_available[chosen_platform]["loading"] += 1
            total_available -= 1

        return {
            "suggestions": suggestions,
            "total_ready": len(ready),
            "skipped_no_platform": len(skipped_no_platform),
            "platform_status": platform_available
        }

    def export_report_json(self, filepath: str, cargo_type: Optional[CargoType] = None,
                           carrier: Optional[str] = None, platform: Optional[str] = None,
                           operator: str = "系统") -> str:
        report = self.get_daily_report(carrier=carrier, cargo_type=cargo_type, platform=platform)
        vehicles = report.vehicles

        filter_info = []
        if carrier:
            filter_info.append(f"承运商={carrier}")
        if cargo_type:
            filter_info.append(f"货类={cargo_type.value}")
        if platform:
            filter_info.append(f"月台={platform}")
        filter_str = ", ".join(filter_info) if filter_info else "无筛选"

        export_data = {
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_date": report.date,
            "filters": {
                "carrier": carrier,
                "cargo_type": cargo_type.value if cargo_type else None,
                "platform": platform
            },
            "summary": self._compute_vehicle_summary(vehicles),
            "carrier_stats": report.carrier_stats,
            "vehicles": [v.to_dict() for v in vehicles]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        log = OperationLog(
            operation_type=OperationType.EXPORT_REPORT,
            operator=operator,
            description=f"导出JSON报表，{filter_str}，共{len(vehicles)}条记录",
        )
        self.add_log(log)
        return filepath

    def export_report_csv(self, filepath: str, cargo_type: Optional[CargoType] = None,
                          carrier: Optional[str] = None, platform: Optional[str] = None,
                          operator: str = "系统") -> str:
        vehicles = self.filter_vehicles(carrier=carrier, cargo_type=cargo_type, platform=platform)

        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["排队号", "车牌号", "司机电话", "货类", "承运商", "预约时段",
                            "签到时间", "状态", "月台", "叫号时间", "开始时间", "完成时间",
                            "停留时长(分钟)", "延迟原因", "延迟备注", "危险品等级", "冷藏温度"])
            for v in vehicles:
                stay = v.stay_minutes() or ""
                writer.writerow([
                    v.queue_number, v.plate_number, v.driver_phone, v.cargo_type.value,
                    v.carrier, v.appointment_time, v.checkin_time, v.status.value,
                    v.platform or "", v.call_time or "", v.start_time or "", v.finish_time or "",
                    stay, v.delay_reason.value if v.delay_reason else "",
                    v.delay_note or "", v.dangerous_level or "", v.temperature_required or ""
                ])

        filter_info = []
        if carrier:
            filter_info.append(f"承运商={carrier}")
        if cargo_type:
            filter_info.append(f"货类={cargo_type.value}")
        if platform:
            filter_info.append(f"月台={platform}")
        filter_str = ", ".join(filter_info) if filter_info else "无筛选"

        log = OperationLog(
            operation_type=OperationType.EXPORT_REPORT,
            operator=operator,
            description=f"导出CSV明细，{filter_str}，共{len(vehicles)}条记录",
        )
        self.add_log(log)
        return filepath
