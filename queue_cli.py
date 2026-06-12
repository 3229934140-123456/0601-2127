#!/usr/bin/env python3
"""公路运输装卸排队命令行工具"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional

from models import Vehicle, CargoType, VehicleStatus, DelayReason, OperationType
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
  # 车辆签到
  queue checkin --plate 京A12345 --phone 13800138000 --cargo dangerous --carrier 顺丰 --appointment "09:00" --operator 张三

  # CSV批量导入
  queue checkin --import appointment.csv --operator 张三

  # 查看等待车辆
  queue call --list

  # 调度建议模式
  queue call --suggest --count 3 --operator 张三

  # 批量叫号（自动跳过延迟车辆）
  queue call --count 3 --platform A1 --operator 张三

  # 指定叫号
  queue call --queue 5,6,7 --platform B2 --operator 张三

  # 调整月台
  queue call --set-platform 5 C1 --operator 张三

  # 标记延迟
  queue delay --queue 5 --reason late --note "司机堵车" --operator 张三

  # 开始装卸
  queue finish --queue 5 --start --operator 张三

  # 完成装卸
  queue finish --queue 5 --operator 张三

  # 查看操作日志
  queue logs --limit 20

  # 组合筛选报表
  queue report --carrier 顺丰物流 --platform A1 --carrier-stats --operator 张三

  # 导出筛选后的报表
  queue report --dangerous --export dangerous_report.json --operator 张三
            """
        )
        parser.add_argument("--operator", default="系统", help="调度员姓名，用于操作日志记录")
        subparsers = parser.add_subparsers(dest="command", required=True, help="可用命令")

        self._add_checkin_parser(subparsers)
        self._add_call_parser(subparsers)
        self._add_delay_parser(subparsers)
        self._add_finish_parser(subparsers)
        self._add_report_parser(subparsers)
        self._add_logs_parser(subparsers)

        return parser

    def _add_checkin_parser(self, subparsers):
        parser = subparsers.add_parser("checkin", help="车辆签到或CSV批量导入")
        parser.add_argument("--import", dest="import_csv", help="从CSV文件批量导入预约车辆")
        parser.add_argument("--plate", help="车牌号 (如: 京A12345)")
        parser.add_argument("--phone", help="司机电话")
        parser.add_argument("--cargo", choices=["general", "dangerous", "refrigerated", "bulk", "container"],
                            help="货类: general(普通), dangerous(危险品), refrigerated(冷藏), bulk(散装), container(集装箱)")
        parser.add_argument("--carrier", help="承运商名称")
        parser.add_argument("--appointment", help="预约时段 (如: 09:00 或 2026-06-12 09:00)")
        parser.add_argument("--dangerous-level", help="危险品等级 (危险品必填)")
        parser.add_argument("--temperature", help="冷藏温度要求 (冷藏货必填)")

    def _add_call_parser(self, subparsers):
        parser = subparsers.add_parser("call", help="查询等待车辆、批量叫号、调度建议、调整月台")
        parser.add_argument("--list", action="store_true", help="列出当前所有等待车辆")
        parser.add_argument("--count", type=int, help="按顺序叫号的数量")
        parser.add_argument("--queue", help="指定叫号的排队号，多个用逗号分隔 (如: 5,6,7)")
        parser.add_argument("--platform", help="指定装卸月台")
        parser.add_argument("--set-platform", nargs=2, metavar=("QUEUE", "PLATFORM"),
                            help="调整指定排队号车辆的月台")
        parser.add_argument("--dangerous", action="store_true", help="只查看危险品车辆")
        parser.add_argument("--refrigerated", action="store_true", help="只查看冷藏车辆")
        parser.add_argument("--include-delayed", action="store_true", help="叫号时包含延迟车辆")
        parser.add_argument("--suggest", action="store_true", help="调度建议模式，按预约时段、货类优先级、月台能力给出建议")

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
        parser = subparsers.add_parser("report", help="统计报表、组合筛选、导出明细、超时提示")
        parser.add_argument("--dangerous", action="store_true", help="只查看危险品车辆")
        parser.add_argument("--refrigerated", action="store_true", help="只查看冷藏车辆")
        parser.add_argument("--carrier", help="按承运商筛选")
        parser.add_argument("--platform", help="按月台筛选")
        parser.add_argument("--export", help="导出JSON报告到指定文件")
        parser.add_argument("--carrier-stats", action="store_true", help="按承运商统计停留时长（基于筛选结果）")
        parser.add_argument("--overtime", action="store_true", help="只查看超时等待车辆")
        parser.add_argument("--threshold", type=int, default=120, help="超时阈值（分钟），默认120分钟")

    def _add_logs_parser(self, subparsers):
        parser = subparsers.add_parser("logs", help="查看当天操作日志（交接班核对）")
        parser.add_argument("--limit", type=int, default=50, help="显示最近N条记录，默认50条")
        parser.add_argument("--operator", help="按调度员筛选")
        parser.add_argument("--type", choices=["checkin", "call", "platform", "start", "finish", "delay", "import", "export"],
                            help="按操作类型筛选")

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

    def _parse_operation_type(self, op_type: str) -> OperationType:
        mapping = {
            "checkin": OperationType.CHECKIN,
            "call": OperationType.CALL,
            "platform": OperationType.PLATFORM_CHANGE,
            "start": OperationType.START_LOADING,
            "finish": OperationType.FINISH_LOADING,
            "delay": OperationType.MARK_DELAY,
            "import": OperationType.BATCH_IMPORT,
            "export": OperationType.EXPORT_REPORT
        }
        return mapping[op_type]

    def _format_time(self, time_str: Optional[str]) -> str:
        if not time_str:
            return "-"
        return time_str

    def _print_vehicle_table(self, vehicles: List[Vehicle], show_details: bool = False):
        if not vehicles:
            print("没有符合条件的车辆记录。")
            return

        header = f"{'号':<4} {'车牌':<12} {'货类':<8} {'承运商':<10} {'状态':<8} {'月台':<6} {'等待/停留':<12} {'签到时间':<20}"
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

            status_str = v.status.value
            if v.status == VehicleStatus.DELAYED:
                status_str = f"[{status_str}]"

            row = f"{v.queue_number:<4} {v.plate_number:<12} {v.cargo_type.value:<8} {v.carrier:<10} {status_str:<8} {v.platform or '-':<6} {wait_str:<12} {v.checkin_time:<20}"
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

    def _print_suggestion(self, suggestion: dict, idx: int):
        print(f"\n  建议 {idx + 1}: #{suggestion['queue_number']} {suggestion['plate_number']}")
        print(f"     货类: {suggestion['cargo_type']} | 承运商: {suggestion['carrier']} | 已等待: {suggestion['waiting_minutes']}分钟")
        print(f"     建议月台: {suggestion['suggested_platform'] or '暂无可用月台'}")
        print(f"     推荐理由: {'，'.join(suggestion['reasons'])}")

    def cmd_checkin(self, args):
        operator = args.operator

        if args.import_csv:
            print(f"\n📥 开始从 CSV 导入: {args.import_csv}")
            print("=" * 60)
            success, skipped, errors, error_details = self.storage.import_from_csv(args.import_csv, operator=operator)
            print(f"✅ 导入完成！成功: {success} | 跳过重复: {skipped} | 格式错误: {errors}")
            print("=" * 60)
            if error_details:
                print("详细信息:")
                for detail in error_details:
                    print(f"  - {detail}")
            print("=" * 60)
            self.check_overtime_vehicles()
            return

        required_args = [args.plate, args.phone, args.cargo, args.carrier, args.appointment]
        if not all(required_args):
            print("错误：单个签到必须提供 --plate, --phone, --cargo, --carrier, --appointment 参数")
            print("或使用 --import 进行批量导入")
            sys.exit(1)

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

        vehicle = self.storage.add_vehicle(vehicle, operator=operator)

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
        print(f"操作人: {operator}")
        print("=" * 50)

        self.check_overtime_vehicles()

    def cmd_call(self, args):
        operator = args.operator

        if args.set_platform:
            queue_num = int(args.set_platform[0])
            platform = args.set_platform[1]
            v = self.storage.set_platform(queue_num, platform, operator=operator)
            if v:
                print(f"✅ 已将 #{queue_num} {v.plate_number} 的月台调整为 {platform}")
            else:
                print(f"错误：未找到排队号为 {queue_num} 的车辆")
            return

        if args.suggest:
            count = args.count or 3
            print(f"\n🤖 调度建议分析中... (建议 {count} 辆车)")
            print("=" * 70)
            suggestion = self.storage.get_dispatch_suggestion(count=count)

            if not suggestion["suggestions"]:
                print(f"❌ {suggestion.get('reason', '没有可调度的车辆')}")
                return

            print(f"📊 当前月台使用情况:")
            for platform, status in suggestion["platform_status"].items():
                bar = "█" * status["loading"] + "░" * (status["capacity"] - status["loading"])
                print(f"   {platform}: {bar} {status['loading']}/{status['capacity']}")

            print(f"\n💡 推荐叫号顺序 (共 {suggestion['total_ready']} 辆待调度):")
            print("-" * 70)
            for i, s in enumerate(suggestion["suggestions"]):
                self._print_suggestion(s, i)

            print("\n" + "-" * 70)
            confirm = input("是否确认按以上建议叫号？(y/N): ")
            if confirm.lower() == 'y':
                for s in suggestion["suggestions"]:
                    if s["suggested_platform"]:
                        self.storage.call_specific_vehicles(
                            [s["queue_number"]], platform=s["suggested_platform"], operator=operator
                        )
                print(f"\n✅ 已按建议叫号 {len(suggestion['suggestions'])} 辆车！")
            else:
                print("已取消叫号。")
            self.check_overtime_vehicles()
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
            normal = [v for v in vehicles if v.status == VehicleStatus.WAITING]
            delayed = [v for v in vehicles if v.status == VehicleStatus.DELAYED]
            print(f"\n📋 当前等待车辆列表 (正常: {len(normal)}, 延迟: {len(delayed)}):")
            self._print_vehicle_table(vehicles, show_details=True)
            if delayed:
                print(f"\nℹ️  延迟车辆共 {len(delayed)} 辆，批量叫号时默认跳过，使用 --include-delayed 可包含")
        elif args.count:
            include_delayed = getattr(args, 'include_delayed', False)
            called = self.storage.call_vehicles(args.count, args.platform, include_delayed=include_delayed, operator=operator)
            if called:
                print(f"\n📢 已叫号 {len(called)} 辆车：")
                for v in called:
                    platform_info = f"，前往月台 {v.platform}" if v.platform else ""
                    delay_info = " (延迟车)" if v.status == VehicleStatus.DELAYED else ""
                    print(f"  #{v.queue_number} {v.plate_number} ({v.carrier}){platform_info}{delay_info}")
            else:
                print("\n没有可叫号的等待车辆。")
                if not include_delayed:
                    delayed = [v for v in self.storage.get_waiting_vehicles() if v.status == VehicleStatus.DELAYED]
                    if delayed:
                        print(f"提示：有 {len(delayed)} 辆延迟车辆，使用 --include-delayed 可叫号")
        elif args.queue:
            queue_numbers = [int(x.strip()) for x in args.queue.split(',')]
            called = self.storage.call_specific_vehicles(queue_numbers, args.platform, operator=operator)
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
        operator = args.operator
        reason = self._parse_delay_reason(args.reason)
        v = self.storage.mark_delay(args.queue, reason, args.note, operator=operator)
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
            print(f"操作人: {operator}")
            print("=" * 50)
            print("\nℹ️  此车辆将留在等待列表中，但批量叫号时会自动跳过")
            print("   使用 call --include-delayed 可强制叫号延迟车辆")
        else:
            print(f"错误：未找到排队号为 {args.queue} 的车辆")

    def cmd_finish(self, args):
        operator = args.operator
        if args.start:
            v = self.storage.start_loading(args.queue, operator=operator)
            if v:
                print("\n" + "=" * 50)
                print("✅ 开始装卸！")
                print("=" * 50)
                print(f"排队号: #{v.queue_number}")
                print(f"车牌号: {v.plate_number}")
                print(f"月台: {v.platform or '未分配'}")
                print(f"开始时间: {v.start_time}")
                print(f"当前状态: {v.status.value}")
                print(f"操作人: {operator}")
                print("=" * 50)
            else:
                print(f"错误：未找到排队号为 {args.queue} 的车辆，或车辆状态不是'已叫号'")
        else:
            v = self.storage.finish_loading(args.queue, operator=operator)
            if v:
                stay = v.stay_minutes()
                print("\n" + "=" * 50)
                print("✅ 装卸完成！")
                print("=" * 50)
                print(f"排队号: #{v.queue_number}")
                print(f"车牌号: {v.plate_number}")
                print(f"月台: {v.platform or '未分配'}")
                print(f"开始时间: {v.start_time}")
                print(f"完成时间: {v.finish_time}")
                print(f"停留时长: {stay} 分钟")
                print(f"当前状态: {v.status.value}")
                print(f"操作人: {operator}")
                print("=" * 50)
            else:
                print(f"错误：未找到排队号为 {args.queue} 的车辆，或车辆状态不是'装卸中'")

        self.check_overtime_vehicles()

    def cmd_report(self, args):
        operator = args.operator
        carrier = args.carrier
        platform = args.platform
        cargo_type = None

        if args.dangerous:
            cargo_type = CargoType.DANGEROUS
            print("\n📊 危险品车辆报告")
        elif args.refrigerated:
            cargo_type = CargoType.REFRIGERATED
            print("\n📊 冷藏车辆报告")
        elif args.overtime:
            print(f"\n📊 超时等待车辆报告 (阈值: {args.threshold}分钟)")
        else:
            print("\n📊 今日排队汇总报告")

        filters = []
        if carrier:
            filters.append(f"承运商={carrier}")
        if platform:
            filters.append(f"月台={platform}")
        if cargo_type:
            filters.append(f"货类={cargo_type.value}")

        if args.overtime:
            vehicles = self.storage.get_overtime_vehicles(args.threshold)
            if carrier:
                vehicles = [v for v in vehicles if v.carrier == carrier]
            if platform:
                vehicles = [v for v in vehicles if v.platform == platform]
        else:
            report = self.storage.get_daily_report(carrier=carrier, cargo_type=cargo_type, platform=platform)
            vehicles = report.vehicles

        print("=" * 70)
        if filters:
            print(f"筛选条件: {' | '.join(filters)}")
        print(f"报告日期: {datetime.now().strftime('%Y-%m-%d')}")
        print(f"总车辆数: {len(vehicles)}")

        if not args.overtime and not args.dangerous and not args.refrigerated:
            waiting = len([v for v in vehicles if v.status == VehicleStatus.WAITING])
            loading = len([v for v in vehicles if v.status == VehicleStatus.LOADING])
            finished = len([v for v in vehicles if v.status == VehicleStatus.FINISHED])
            delayed = len([v for v in vehicles if v.status == VehicleStatus.DELAYED])
            overtime = len([v for v in vehicles if v.is_overtime(args.threshold)])
            finished_vehicles = [v for v in vehicles if v.status == VehicleStatus.FINISHED]
            total_stay = sum(v.stay_minutes() or 0 for v in finished_vehicles)
            avg_stay = round(total_stay / len(finished_vehicles), 1) if finished_vehicles else 0
            print(f"等待中: {waiting} | 装卸中: {loading} | 已完成: {finished} | 延迟: {delayed}")
            print(f"超时等待: {overtime} | 平均停留时长: {avg_stay} 分钟")
        print("=" * 70)

        if args.carrier_stats and not args.overtime:
            print("\n📈 承运商停留时长统计（基于当前筛选结果）：")
            print("-" * 70)
            stats = self.storage.get_carrier_stats(vehicles)
            if stats:
                print(f"{'承运商':<15} {'总车辆':<8} {'已完成':<8} {'平均停留(分钟)':<15} {'总停留(分钟)':<15}")
                print("-" * 70)
                for s in stats:
                    print(f"{s['carrier']:<15} {s['total']:<8} {s['finished']:<8} {s['avg_stay_minutes']:<15} {s['total_stay_minutes']:<15}")
            else:
                print("暂无统计数据")

        print(f"\n📋 车辆明细：")
        self._print_vehicle_table(vehicles, show_details=True)

        if args.export:
            filepath = self.storage.export_report(
                args.export, cargo_type=cargo_type, carrier=carrier, platform=platform, operator=operator
            )
            print(f"\n✅ 报告已导出到: {filepath}")
            print(f"   筛选条件已应用到导出数据")

        self.check_overtime_vehicles(args.threshold)

    def cmd_logs(self, args):
        op_type = self._parse_operation_type(args.type) if args.type else None
        logs = self.storage.get_logs(operator=args.operator, operation_type=op_type)
        logs = logs[:args.limit]

        print("\n📋 操作日志（最近操作在最前）")
        print("=" * 90)
        print(f"{'时间':<20} {'操作人':<10} {'操作类型':<12} {'排队号':<6} {'车牌':<12} 详情")
        print("-" * 90)

        for log in logs:
            queue_str = f"#{log.queue_number}" if log.queue_number else "-"
            plate_str = log.plate_number or "-"
            print(f"{log.timestamp:<20} {log.operator:<10} {log.operation_type.value:<12} {queue_str:<6} {plate_str:<12} {log.description}")

        print("=" * 90)
        print(f"共显示 {len(logs)} 条记录")

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
            elif parsed_args.command == "logs":
                self.cmd_logs(parsed_args)
        except KeyboardInterrupt:
            print("\n操作已取消。")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


def main():
    cli = QueueCLI()
    cli.run()


if __name__ == "__main__":
    main()
