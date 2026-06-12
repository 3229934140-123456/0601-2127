import json
import os
import csv
from datetime import datetime, date
from typing import List, Optional, Dict, Tuple
from collections import defaultdict

from models import Vehicle, VehicleStatus, CargoType, DelayReason, DailyReport, OperationLog, OperationType


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

    def get_logs(self, operator: Optional[str] = None, operation_type: Optional[OperationType] = None) -> List[OperationLog]:
        data = self._read_data()
        logs = [OperationLog.from_dict(l) for l in data.get("logs", [])]
        if operator:
            logs = [l for l in logs if l.operator == operator]
        if operation_type:
            logs = [l for l in logs if l.operation_type == operation_type]
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs

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

    def get_daily_report(self, carrier: Optional[str] = None, cargo_type: Optional[CargoType] = None,
                         platform: Optional[str] = None) -> DailyReport:
        vehicles = self.filter_vehicles(carrier=carrier, cargo_type=cargo_type, platform=platform)
        finished = [v for v in vehicles if v.status == VehicleStatus.FINISHED]
        total_stay = sum(v.stay_minutes() or 0 for v in finished)
        avg_stay = total_stay / len(finished) if finished else 0

        all_vehicles = self.get_all_vehicles()
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

    def import_from_csv(self, filepath: str, operator: str = "系统") -> Tuple[int, int, int, List[str]]:
        success = 0
        skipped = 0
        errors = 0
        error_details = []

        existing_plates = {v.plate_number for v in self.get_all_vehicles()
                          if v.status not in [VehicleStatus.FINISHED, VehicleStatus.CANCELLED]}

        cargo_type_map = {
            '普通货物': CargoType.GENERAL, '普通': CargoType.GENERAL, 'general': CargoType.GENERAL,
            '危险品': CargoType.DANGEROUS, 'dangerous': CargoType.DANGEROUS,
            '冷藏货物': CargoType.REFRIGERATED, '冷藏': CargoType.REFRIGERATED, 'refrigerated': CargoType.REFRIGERATED,
            '散装货物': CargoType.BULK, '散装': CargoType.BULK, 'bulk': CargoType.BULK,
            '集装箱': CargoType.CONTAINER, 'container': CargoType.CONTAINER
        }

        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                required_cols = {'plate', 'phone', 'cargo', 'carrier', 'appointment'}
                if not required_cols.issubset(set(reader.fieldnames or [])):
                    missing = required_cols - set(reader.fieldnames or [])
                    return 0, 0, 1, [f"缺少必要列: {', '.join(missing)}"]

                for row_num, row in enumerate(reader, start=2):
                    try:
                        plate = row.get('plate', '').strip()
                        phone = row.get('phone', '').strip()
                        cargo_str = row.get('cargo', '').strip()
                        carrier = row.get('carrier', '').strip()
                        appointment = row.get('appointment', '').strip()
                        dangerous_level = row.get('dangerous_level', '').strip() or None
                        temperature = row.get('temperature', '').strip() or None

                        if not all([plate, phone, cargo_str, carrier, appointment]):
                            errors += 1
                            error_details.append(f"第{row_num}行: 缺少必填字段")
                            continue

                        if plate in existing_plates:
                            skipped += 1
                            error_details.append(f"第{row_num}行: 车牌 {plate} 已在排队中，已跳过")
                            continue

                        cargo_type = cargo_type_map.get(cargo_str.lower())
                        if not cargo_type:
                            errors += 1
                            error_details.append(f"第{row_num}行: 无效货类 '{cargo_str}'")
                            continue

                        if cargo_type == CargoType.DANGEROUS and not dangerous_level:
                            errors += 1
                            error_details.append(f"第{row_num}行: 危险品缺少 dangerous_level")
                            continue

                        if cargo_type == CargoType.REFRIGERATED and not temperature:
                            errors += 1
                            error_details.append(f"第{row_num}行: 冷藏货缺少 temperature")
                            continue

                        if len(appointment) <= 5 and ':' in appointment:
                            today = date.today().strftime("%Y-%m-%d")
                            appointment = f"{today} {appointment}:00"

                        vehicle = Vehicle(
                            plate_number=plate,
                            driver_phone=phone,
                            cargo_type=cargo_type,
                            carrier=carrier,
                            appointment_time=appointment,
                            dangerous_level=dangerous_level,
                            temperature_required=temperature
                        )
                        self.add_vehicle(vehicle, operator=operator)
                        existing_plates.add(plate)
                        success += 1

                    except Exception as e:
                        errors += 1
                        error_details.append(f"第{row_num}行: {str(e)}")

            log = OperationLog(
                operation_type=OperationType.BATCH_IMPORT,
                operator=operator,
                description=f"CSV批量导入完成：成功{success}辆，跳过{skipped}辆，错误{errors}辆",
            )
            self.add_log(log)

        except Exception as e:
            return 0, 0, 1, [f"文件读取失败: {str(e)}"]

        return success, skipped, errors, error_details

    def get_dispatch_suggestion(self, count: int = 3) -> Dict:
        ready = self.get_ready_vehicles()
        if not ready:
            return {"suggestions": [], "reason": "没有可调度的车辆"}

        now = datetime.now()

        def score_vehicle(v: Vehicle) -> Tuple[int, int, int]:
            try:
                appt_time = datetime.strptime(v.appointment_time, "%Y-%m-%d %H:%M:%S")
                appt_priority = 0 if appt_time <= now else 1
            except:
                appt_priority = 1

            cargo_priority = self.CARGO_PRIORITY.get(v.cargo_type, 5)
            queue_priority = v.queue_number

            return (appt_priority, cargo_priority, queue_priority)

        scored = [(score_vehicle(v), v) for v in ready]
        scored.sort(key=lambda x: x[0])

        platform_loading = defaultdict(int)
        for v in self.get_all_vehicles():
            if v.status == VehicleStatus.LOADING and v.platform:
                platform_loading[v.platform] += 1

        suggestions = []
        for (appt_prio, cargo_prio, queue_prio), v in scored[:count]:
            best_platform = None
            min_load = float('inf')
            for platform, capacity in self.PLATFORM_CAPACITY.items():
                current_load = platform_loading.get(platform, 0)
                if current_load < capacity and current_load < min_load:
                    if (v.cargo_type == CargoType.DANGEROUS and platform.startswith('C')) or \
                       (v.cargo_type == CargoType.REFRIGERATED and platform.startswith('B')) or \
                       (platform.startswith('A')):
                        min_load = current_load
                        best_platform = platform

            if not best_platform:
                for platform, capacity in self.PLATFORM_CAPACITY.items():
                    current_load = platform_loading.get(platform, 0)
                    if current_load < capacity and current_load < min_load:
                        min_load = current_load
                        best_platform = platform

            reasons = []
            if appt_prio == 0:
                reasons.append("已到预约时间")
            reasons.append(f"货类优先级{self.CARGO_PRIORITY.get(v.cargo_type, 5)}")
            reasons.append(f"排队号#{v.queue_number}")

            suggestions.append({
                "queue_number": v.queue_number,
                "plate_number": v.plate_number,
                "cargo_type": v.cargo_type.value,
                "carrier": v.carrier,
                "suggested_platform": best_platform,
                "reasons": reasons,
                "waiting_minutes": v.waiting_minutes()
            })
            if best_platform:
                platform_loading[best_platform] += 1

        return {
            "suggestions": suggestions,
            "total_ready": len(ready),
            "platform_status": {p: {"loading": platform_loading.get(p, 0), "capacity": c}
                               for p, c in self.PLATFORM_CAPACITY.items()}
        }

    def export_report(self, filepath: str, cargo_type: Optional[CargoType] = None,
                     carrier: Optional[str] = None, platform: Optional[str] = None, operator: str = "系统") -> str:
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
            "summary": {
                "total_vehicles": len(vehicles),
                "waiting": report.waiting_count,
                "loading": report.loading_count,
                "finished": report.finished_count,
                "delayed": report.delayed_count,
                "overtime": report.overtime_count,
                "avg_stay_minutes": report.avg_stay_minutes
            },
            "carrier_stats": report.carrier_stats,
            "vehicles": [v.to_dict() for v in vehicles]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        log = OperationLog(
            operation_type=OperationType.EXPORT_REPORT,
            operator=operator,
            description=f"导出报表，{filter_str}，共{len(vehicles)}条记录",
        )
        self.add_log(log)

        return filepath
