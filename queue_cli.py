#!/usr/bin/env python3
"""公路运输装卸排队命令行工具"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional

from models import Vehicle, CargoType, VehicleStatus, DelayReason
from storage import QueueStorage


class QueueCLI:
    def __init__(self):
        self.storage = QueueStorage()
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="queue",
            description="公路运输装卸排队管理系统 - 物流场站调度员专用工具",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
命令示例:
  queue checkin --plate 京A12345 --phone 13800138000 --cargo dangerous --carrier 顺丰 --appointment "09:00"
  queue call --list
  queue call --count 3 --platform A1
  queue call --queue 5,6,7 --platform B2
  queue delay --queue 5 --reason late --note "司机堵车"
  queue finish --queue 5 --start
  queue finish --queue 5
  queue report
  queue report --dangerous
  queue report --refrigerated
  queue report --export today_report.json
            """
        )
        subparsers = parser.add_subparsers(dest="command", required=True, help="可用命令")

        self._add_checkin_parser(subparsers)
        self._add_call_parser(subparsers)
        self._add_delay_parser(subparsers)
        self._add_finish_parser(subparsers)
        self._add_report_parser(subparsers)

        return parser

    def _add_checkin_parser(self, subparsers):
        parser = subparsers.add_parser("checkin", help="车辆签到，生成排队号")
        parser.add_argument("--plate", required=True, help="车牌号 (如: 京A12345)")
        parser.add_argument("--phone", required=True, help="司机电话")
        parser.add_argument("--cargo", required=True, choices=["general", "dangerous", "refrigerated", "bulk", "container"],
                            help="货类: general(普通), dangerous(危险品), refrigerated(冷藏), bulk(散装), container(集装箱)")
        parser.add_argument("--carrier", required=True, help="承运商名称")
        parser.add_argument("--appointment", required=True, help="预约时段 (如: 09:00 或 2026-06-12 09:00)")
        parser.add_argument("--dangerous-level", help="危险品等级 (危险品必填)")
        parser.add_argument("--temperature", help="冷藏温度要求 (冷藏货必填)")

    def _add_call_parser(self, subparsers):
        parser = subparsers.add_parser("call", help="查询等待车辆、批量叫号、调整月台")
        parser.add_argument("--list", action="store_true", help="列出当前所有等待车辆")
        parser.add_argument("--count", type=int, help="按顺序叫号的数量")
        parser.add_argument("--queue", help="指定叫号的排队号，多个用逗号分隔 (如: 5,6,7)")
        parser.add_argument("--platform", help="指定装卸月台")
        parser.add_argument("--set-platform", nargs=2, metavar=("QUEUE", "PLATFORM"),
                            help="调整指定排队号车辆的月台")
        parser.add_argument("--dangerous", action="store_true", help="只查看危险品车辆")
        parser.add_argument("--refrigerated", action="store_true", help="只查看冷藏车辆")

    def _add_delay_parser(self, subparsers):
        parser = subparsers.add_parser("delay", help="标记迟到和插队原因")
        parser.add_argument("--queue", type=int, required=True, help="排队号")
        parser.add_argument("--reason", required=True,
                            choices=["late", "document", "carrier", "yard", "equipment", "priority", "other"],
                            help="延迟原因: late(迟到), document(单据问题), carrier(承运商要求), yard(场站调度), equipment(设备故障), priority(优先插队), other(其他)")
        parser.add_argument("--note", help="补充说明")

    def _add_finish_parser(self, subparsers):
        parser = subparsers.add_parser("finish", help="记录开始和完成装卸时间")
        parser.add_argument("--queue", type=int, required=True, help="排队号")
        parser.add_argument("--start", action="store_true", help="标记开始装卸")

    def _add_report_parser(self, subparsers):
        parser = subparsers.add_parser("report", help="统计报表、导出明细、超时提示")
        parser.add_argument("--dangerous", action="store_true", help="只查看危险品车辆")
        parser.add_argument("--refrigerated", action="store_true", help="只查看冷藏车辆")
        parser.add_argument("--export", help="导出JSON报告到指定文件")
        parser.add_argument("--carrier-stats", action="store_true", help="按承运商统计停留时长")
        parser.add_argument("--overtime", action="store_true", help="只查看超时等待车辆")
        parser.add_argument("--threshold", type=int, default=120, help="超时阈值（分钟），默认120分钟")

    def _parse_cargo_type(self, cargo: str) -> CargoType:
        mapping = {
            "general": CargoType.GENERAL,
            "dangerous": CargoType.DANGEROUS,
            "refrigerated": CargoType.REFRIGERATED,
            "bulk": CargoType.BULK,
            "container": CargoType.CONTAINER
        }
        return mapping[cargo]

    def _parse_delay_reason(self, reason: str) -> DelayReason:
        mapping = {
            "late": DelayReason.LATE_ARRIVAL,
            "document": DelayReason.DOCUMENT_ISSUE,
            "carrier": DelayReason.CARRIER_REQUEST,
            "yard": DelayReason.YARD_ARRANGEMENT,
            "equipment": DelayReason.EQUIPMENT_FAILURE,
            "priority": DelayReason.PRIORITY_INSERT,
            "other": DelayReason.OTHER
        }
        return mapping[reason]

    def _format_time(self, time_str: Optional[str]) -> str:
        if not time_str:
            return "-"
        return time_str

    def _print_vehicle_table(self, vehicles: List[Vehicle], show_details: bool = False):
        if not vehicles:
            print("没有符合条件的车辆记录。")
            return

        header = f"{'号':<4} {'车牌':<12} {'货类':<8} {'承运商':<10} {'状态':<8} {'月台':<6} {'等待/停留':<10} {'签到时间':<20}"
        if show_details:
            header += f" {'司机电话':<15} {'预约时段':<20} {'延迟原因':<10}"

        print("=" * len(header))
        print(header)
        print("-" * len(header))

        for v in vehicles:
            wait_time = v.stay_minutes() if v.status == VehicleStatus.FINISHED else v.waiting_minutes()
            wait_str = f"{wait_time}分钟"
            if v.is_overtime() and v.status != VehicleStatus.FINISHED:
                wait_str += " ⚠超时"

            row = f"{v.queue_number:<4} {v.plate_number:<12} {v.cargo_type.value:<8} {v.carrier:<10} {v.status.value:<8} {v.platform or '-':<6} {wait_str:<10} {v.checkin_time:<20}"
            if show_details:
                delay_reason = v.delay_reason.value if v.delay_reason else "-"
                row += f" {v.driver_phone:<15} {v.appointment_time:<20} {delay_reason:<10}"
            print(row)

        print("=" * len(header))
        print(f"共 {len(vehicles)} 辆车")

    def check_overtime_vehicles(self, threshold_minutes: int = 120):
        overtime = self.storage.get_overtime_vehicles(threshold_minutes)
        if overtime:
            print(f"\n⚠️  警告：有 {len(overtime)} 辆车等待超过 {threshold_minutes} 分钟！")
            for v in overtime:
                print(f"   - #{v.queue_number} {v.plate_number} ({v.carrier}) 已等待 {v.waiting_minutes()} 分钟")
            print()

    def cmd_checkin(self, args):
        cargo_type = self._parse_cargo_type(args.cargo)

        if cargo_type == CargoType.DANGEROUS and not args.dangerous_level:
            print("错误：危险品车辆必须指定 --dangerous-level 参数")
            sys.exit(1)
        if cargo_type == CargoType.REFRIGERATED and not args.temperature:
            print("错误：冷藏车辆必须指定 --temperature 参数")
            sys.exit(1)

        existing = self.storage.get_vehicle_by_plate(args.plate)
        if existing and existing.status not in [VehicleStatus.FINISHED, VehicleStatus.CANCELLED]:
            print(f"警告：车牌 {args.plate} 已在排队中，排队号 #{existing.queue_number}，状态: {existing.status.value}")
            confirm = input("是否继续签到？(y/N): ")
            if confirm.lower() != 'y':
                print("已取消签到。")
                return

        appointment = args.appointment
        if len(appointment) <= 5 and ':' in appointment:
            today = datetime.now().strftime("%Y-%m-%d")
            appointment = f"{today} {appointment}:00"

        vehicle = Vehicle(
            plate_number=args.plate,
            driver_phone=args.phone,
            cargo_type=cargo_type,
            carrier=args.carrier,
            appointment_time=appointment,
            dangerous_level=args.dangerous_level,
            temperature_required=args.temperature
        )

        vehicle = self.storage.add_vehicle(vehicle)

        print("\n" + "=" * 50)
        print("✅ 车辆签到成功！")
        print("=" * 50)
        print(f"排队号: #{vehicle.queue_number}")
        print(f"车牌号: {vehicle.plate_number}")
        print(f"司机电话: {vehicle.driver_phone}")
        print(f"货类: {vehicle.cargo_type.value}")
        if vehicle.dangerous_level:
            print(f"危险品等级: {vehicle.dangerous_level}")
        if vehicle.temperature_required:
            print(f"温度要求: {vehicle.temperature_required}")
        print(f"承运商: {vehicle.carrier}")
        print(f"预约时段: {vehicle.appointment_time}")
        print(f"签到时间: {vehicle.checkin_time}")
        print(f"当前状态: {vehicle.status.value}")
        print("=" * 50)

        self.check_overtime_vehicles()

    def cmd_call(self, args):
        if args.set_platform:
            queue_num = int(args.set_platform[0])
            platform = args.set_platform[1]
            v = self.storage.set_platform(queue_num, platform)
            if v:
                print(f"✅ 已将 #{queue_num} {v.plate_number} 的月台调整为 {platform}")
            else:
                print(f"错误：未找到排队号为 {queue_num} 的车辆")
            return

        if args.dangerous:
            vehicles = [v for v in self.storage.get_waiting_vehicles() if v.cargo_type == CargoType.DANGEROUS]
            print("\n📋 危险品等待车辆列表：")
            self._print_vehicle_table(vehicles, show_details=True)
        elif args.refrigerated:
            vehicles = [v for v in self.storage.get_waiting_vehicles() if v.cargo_type == CargoType.REFRIGERATED]
            print("\n📋 冷藏货物等待车辆列表：")
            self._print_vehicle_table(vehicles, show_details=True)
        elif args.list:
            vehicles = self.storage.get_waiting_vehicles()
            print("\n📋 当前等待车辆列表：")
            self._print_vehicle_table(vehicles, show_details=True)
        elif args.count:
            called = self.storage.call_vehicles(args.count, args.platform)
            if called:
                print(f"\n📢 已叫号 {len(called)} 辆车：")
                for v in called:
                    platform_info = f"，前往月台 {v.platform}" if v.platform else ""
                    print(f"  #{v.queue_number} {v.plate_number} ({v.carrier}){platform_info}")
            else:
                print("\n没有可叫号的等待车辆。")
        elif args.queue:
            queue_numbers = [int(x.strip()) for x in args.queue.split(',')]
            called = self.storage.call_specific_vehicles(queue_numbers, args.platform)
            if called:
                print(f"\n📢 已叫号 {len(called)} 辆车：")
                for v in called:
                    platform_info = f"，前往月台 {v.platform}" if v.platform else ""
                    print(f"  #{v.queue_number} {v.plate_number} ({v.carrier}){platform_info}")
            else:
                print("\n没有可叫号的车辆。")
        else:
            vehicles = self.storage.get_waiting_vehicles()
            print("\n📋 当前等待车辆列表：")
            self._print_vehicle_table(vehicles)

        self.check_overtime_vehicles()

    def cmd_delay(self, args):
        reason = self._parse_delay_reason(args.reason)
        v = self.storage.mark_delay(args.queue, reason, args.note)
        if v:
            print("\n" + "=" * 50)
            print("✅ 延迟标记成功！")
            print("=" * 50)
            print(f"排队号: #{v.queue_number}")
            print(f"车牌号: {v.plate_number}")
            print(f"延迟原因: {v.delay_reason.value}")
            if v.delay_note:
                print(f"补充说明: {v.delay_note}")
            print(f"标记时间: {v.delay_time}")
            print(f"当前状态: {v.status.value}")
            print("=" * 50)
        else:
            print(f"错误：未找到排队号为 {args.queue} 的车辆")

    def cmd_finish(self, args):
        if args.start:
            v = self.storage.start_loading(args.queue)
            if v:
                print("\n" + "=" * 50)
                print("✅ 开始装卸！")
                print("=" * 50)
                print(f"排队号: #{v.queue_number}")
                print(f"车牌号: {v.plate_number}")
                print(f"开始时间: {v.start_time}")
                print(f"当前状态: {v.status.value}")
                print("=" * 50)
            else:
                print(f"错误：未找到排队号为 {args.queue} 的车辆，或车辆状态不是'已叫号'")
        else:
            v = self.storage.finish_loading(args.queue)
            if v:
                stay = v.stay_minutes()
                print("\n" + "=" * 50)
                print("✅ 装卸完成！")
                print("=" * 50)
                print(f"排队号: #{v.queue_number}")
                print(f"车牌号: {v.plate_number}")
                print(f"开始时间: {v.start_time}")
                print(f"完成时间: {v.finish_time}")
                print(f"停留时长: {stay} 分钟")
                print(f"当前状态: {v.status.value}")
                print("=" * 50)
            else:
                print(f"错误：未找到排队号为 {args.queue} 的车辆，或车辆状态不是'装卸中'")

        self.check_overtime_vehicles()

    def cmd_report(self, args):
        report = self.storage.get_daily_report()
        vehicles = report.vehicles

        if args.dangerous:
            vehicles = [v for v in vehicles if v.cargo_type == CargoType.DANGEROUS]
            print("\n📊 危险品车辆报告")
        elif args.refrigerated:
            vehicles = [v for v in vehicles if v.cargo_type == CargoType.REFRIGERATED]
            print("\n📊 冷藏车辆报告")
        elif args.overtime:
            vehicles = self.storage.get_overtime_vehicles(args.threshold)
            print(f"\n📊 超时等待车辆报告 (阈值: {args.threshold}分钟)")
        else:
            print("\n📊 今日排队汇总报告")

        print("=" * 60)
        print(f"报告日期: {report.date}")
        print(f"总车辆数: {len(vehicles)}")

        if not args.overtime and not args.dangerous and not args.refrigerated:
            print(f"等待中: {report.waiting_count} | 装卸中: {report.loading_count} | 已完成: {report.finished_count} | 延迟: {report.delayed_count}")
            print(f"超时等待: {report.overtime_count} | 平均停留时长: {report.avg_stay_minutes} 分钟")
        print("=" * 60)

        if args.carrier_stats and not args.overtime:
            print("\n📈 承运商停留时长统计：")
            print("-" * 60)
            stats = report.carrier_stats
            if stats:
                print(f"{'承运商':<15} {'总车辆':<8} {'已完成':<8} {'平均停留(分钟)':<15} {'总停留(分钟)':<15}")
                print("-" * 60)
                for s in stats:
                    print(f"{s['carrier']:<15} {s['total']:<8} {s['finished']:<8} {s['avg_stay_minutes']:<15} {s['total_stay_minutes']:<15}")
            else:
                print("暂无统计数据")

        print(f"\n📋 车辆明细：")
        self._print_vehicle_table(vehicles, show_details=True)

        if args.export:
            cargo_type = None
            if args.dangerous:
                cargo_type = CargoType.DANGEROUS
            elif args.refrigerated:
                cargo_type = CargoType.REFRIGERATED

            filepath = self.storage.export_report(args.export, cargo_type)
            print(f"\n✅ 报告已导出到: {filepath}")

        self.check_overtime_vehicles(args.threshold)

    def run(self, args=None):
        parsed_args = self.parser.parse_args(args)

        try:
            if parsed_args.command == "checkin":
                self.cmd_checkin(parsed_args)
            elif parsed_args.command == "call":
                self.cmd_call(parsed_args)
            elif parsed_args.command == "delay":
                self.cmd_delay(parsed_args)
            elif parsed_args.command == "finish":
                self.cmd_finish(parsed_args)
            elif parsed_args.command == "report":
                self.cmd_report(parsed_args)
        except KeyboardInterrupt:
            print("\n操作已取消。")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            sys.exit(1)


def main():
    cli = QueueCLI()
    cli.run()


if __name__ == "__main__":
    main()
