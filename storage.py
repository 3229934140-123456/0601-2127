import json
import os
from datetime import datetime, date
from typing import List, Optional, Dict
from collections import defaultdict

from models import Vehicle, VehicleStatus, CargoType, DelayReason, DailyReport


class QueueStorage:
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
                json.dump({"vehicles": [], "last_queue_number": 0}, f, ensure_ascii=False, indent=2)

    def _read_data(self) -> dict:
        filepath = self._get_today_file()
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_data(self, data: dict):
        filepath = self._get_today_file()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_next_queue_number(self) -> int:
        data = self._read_data()
        next_num = data.get("last_queue_number", 0) + 1
        data["last_queue_number"] = next_num
        self._write_data(data)
        return next_num

    def add_vehicle(self, vehicle: Vehicle) -> Vehicle:
        data = self._read_data()
        if vehicle.queue_number == 0:
            next_num = data.get("last_queue_number", 0) + 1
            data["last_queue_number"] = next_num
            vehicle.queue_number = next_num
        data["vehicles"].append(vehicle.to_dict())
        self._write_data(data)
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

    def call_vehicles(self, count: int = 1, platform: Optional[str] = None) -> List[Vehicle]:
        waiting = self.get_waiting_vehicles()
        called = []
        for v in waiting[:count]:
            if v.status == VehicleStatus.WAITING:
                v.status = VehicleStatus.CALLED
                v.call_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if platform:
                    v.platform = platform
                self.update_vehicle(v)
                called.append(v)
        return called

    def call_specific_vehicles(self, queue_numbers: List[int], platform: Optional[str] = None) -> List[Vehicle]:
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
        return called

    def set_platform(self, queue_number: int, platform: str) -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v:
            v.platform = platform
            self.update_vehicle(v)
            return v
        return None

    def mark_delay(self, queue_number: int, reason: DelayReason, note: Optional[str] = None) -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v:
            v.status = VehicleStatus.DELAYED
            v.delay_reason = reason
            v.delay_note = note
            v.delay_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_vehicle(v)
            return v
        return None

    def start_loading(self, queue_number: int) -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v and v.status == VehicleStatus.CALLED:
            v.status = VehicleStatus.LOADING
            v.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_vehicle(v)
            return v
        return None

    def finish_loading(self, queue_number: int) -> Optional[Vehicle]:
        v = self.get_vehicle_by_queue(queue_number)
        if v and v.status == VehicleStatus.LOADING:
            v.status = VehicleStatus.FINISHED
            v.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_vehicle(v)
            return v
        return None

    def get_carrier_stats(self) -> List[dict]:
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

    def get_daily_report(self) -> DailyReport:
        vehicles = self.get_all_vehicles()
        finished = [v for v in vehicles if v.status == VehicleStatus.FINISHED]
        total_stay = sum(v.stay_minutes() or 0 for v in finished)
        avg_stay = total_stay / len(finished) if finished else 0

        return DailyReport(
            date=date.today().strftime("%Y-%m-%d"),
            total_vehicles=len(vehicles),
            waiting_count=len([v for v in vehicles if v.status == VehicleStatus.WAITING]),
            loading_count=len([v for v in vehicles if v.status == VehicleStatus.LOADING]),
            finished_count=len(finished),
            delayed_count=len([v for v in vehicles if v.status == VehicleStatus.DELAYED]),
            overtime_count=len(self.get_overtime_vehicles()),
            avg_stay_minutes=round(avg_stay, 1),
            carrier_stats=self.get_carrier_stats(),
            vehicles=vehicles
        )

    def export_report(self, filepath: str, cargo_type: Optional[CargoType] = None) -> str:
        report = self.get_daily_report()
        vehicles = report.vehicles
        if cargo_type:
            vehicles = [v for v in vehicles if v.cargo_type == cargo_type]

        export_data = {
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_date": report.date,
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
        return filepath
