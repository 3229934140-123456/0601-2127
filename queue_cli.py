#!/usr/bin/env python3
"""公路运输装卸排队命令行工具"""

import argparse
import sys
import os
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
  # 车辆签到（--operator 可以放在主命令或子命令后面）
  queue checkin --plate 京A12345 --phone 13800138000 --cargo dangerous --carrier 顺丰 --appointment "09:00" --operator 张三
  queue --operator 张三 checkin --plate 京A12345 --phone 13800138000 --cargo dangerous --carrier 顺丰 --appointment "09:00"

  # CSV批量导入（带预检确认）
  queue checkin --import appointment.csv --operator 张三

  # 查看等待车辆（支持全部5种货类筛选）
  queue call --list --general
  queue call --list --bulk
  queue call --list --container
  queue call --list --dangerous
  queue call --list --refrigerated

  # 调度建议模式
  queue call --suggest --count 3 --operator 张三

  # 批量叫号（自动跳过延迟车辆）
  queue call --count 3 --platform A1 --operator 张三

  # 指定叫号
  queue call --queue 5,6,7 --platform B2 --operator 张三

  # 调整月台
  queue call --set-platform 5 C1 --operator 张三

  # 标记延迟 / 恢复排队 / 取消排队 / 改预约时段
  queue delay --queue 5 --reason late --note "司机堵车" --operator 张三
  queue delay --queue 5 --resume --operator 张三
  queue delay --queue 5 --cancel --operator 张三
  queue delay --queue 5 --change-appointment "14:00" --operator 张三

  # 开始装卸 / 完成装卸
  queue finish --queue 5 --start --operator 张三
  queue finish --queue 5 --operator 张三

  # 查看操作日志（支持按排队号/车牌/时间段/操作类型查询）
  queue logs --limit 20
  queue logs --queue 5 --plate 京A12345
  queue logs --start "2026-06-12 08:00:00" --end "2026-06-12 16:00:00"

  # 导出交接班日志（每辆车最后一次真实状态变化）
  queue logs --export-shift shift_log.json --start "2026-06-12 08:00:00" --end "2026-06-12 16:00:00"

  # 交接班班次视图（按早/中/晚班分组导出）
  queue logs --export-shift shift_morning.json --shift 早班
  queue logs --export-shift shift_afternoon.json --shift 中班
  queue logs --export-shift shift_night.json --shift 晚班

  # 车辆完整时间线（按车牌按时间顺序显示签到→叫号→装卸→完成等节点）
  queue logs --timeline 京A12345
  queue logs --timeline 京A12345 --export-timeline timeline_京A12345.json

  # 组合筛选报表（支持全部5种货类）
  queue report --general --carrier-stats
  queue report --bulk
  queue report --container
  queue report --dangerous --carrier-stats
  queue report --refrigerated
  queue report --carrier 顺丰物流 --platform A1 --carrier-stats --operator 张三

  # 导出筛选后的报表（JSON + CSV明细）
  queue report --general --export general_report.json --export-csv general_detail.csv
            """
        )
        parser.add_argument("--operator", default=None, help="调度员姓名，用于操作日志记录，可放在主命令或子命令后面")
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
        parser.add_argument("--operator", default=None, help="调度员姓名（同主参数）")
        parser.add_argument("--import", dest="import_csv", help="从CSV文件批量导入预约车辆（带预检确认）")
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
        parser.add_argument("--operator", default=None, help="调度员姓名（同主参数）")
        parser.add_argument("--list", action="store_true", help="列出当前所有等待车辆")
        parser.add_argument("--count", type=int, help="按顺序叫号的数量")
        parser.add_argument("--queue", help="指定叫号的排队号，多个用逗号分隔 (如: 5,6,7)")
        parser.add_argument("--platform", help="指定装卸月台")
        parser.add_argument("--set-platform", nargs=2, metavar=("QUEUE", "PLATFORM"),
                            help="调整指定排队号车辆的月台")
        parser.add_argument("--general", action="store_true", help="只查看普通货物车辆")
        parser.add_argument("--bulk", action="store_true", help="只查看散装货物车辆")
        parser.add_argument("--container", action="store_true", help="只查看集装箱车辆")
        parser.add_argument("--dangerous", action="store_true", help="只查看危险品车辆")
        parser.add_argument("--refrigerated", action="store_true", help="只查看冷藏车辆")
        parser.add_argument("--include-delayed", action="store_true", help="叫号时包含延迟车辆")
        parser.add_argument("--suggest", action="store_true", help="调度建议模式，按预约时段、货类优先级、月台适配给出建议")

    def _add_delay_parser(self, subparsers):
        parser = subparsers.add_parser("delay", help="标记延迟 / 恢复排队 / 取消排队 / 改预约时段")
        parser.add_argument("--operator", default=None, help="调度员姓名（同主参数）")
        parser.add_argument("--queue", type=int, required=True, help="排队号")
        parser.add_argument("--reason",
                            choices=["late", "document", "carrier", "yard", "equipment", "priority", "other"],
                            help="延迟原因: late(迟到), document(单据问题), carrier(承运商要求), yard(场站调度), equipment(设备故障), priority(优先插队), other(其他)")
        parser.add_argument("--note", help="补充说明")
        parser.add_argument("--resume", action="store_true", help="恢复排队（将延迟车辆恢复为等待中）")
        parser.add_argument("--cancel", action="store_true", help="取消排队")
        parser.add_argument("--change-appointment", dest="change_appointment",
                            help="修改预约时段 (如: 14:00 或 2026-06-12 14:00:00)")

    def _add_finish_parser(self, subparsers):
        parser = subparsers.add_parser("finish", help="记录开始和完成装卸时间")
        parser.add_argument("--operator", default=None, help="调度员姓名（同主参数）")
        parser.add_argument("--queue", type=int, required=True, help="排队号")
        parser.add_argument("--start", action="store_true", help="标记开始装卸")

    def _add_report_parser(self, subparsers):
        parser = subparsers.add_parser("report", help="统计报表、组合筛选、导出明细、超时提示")
        parser.add_argument("--operator", default=None, help="调度员姓名（同主参数）")
        parser.add_argument("--general", action="store_true", help="只查看普通货物车辆")
        parser.add_argument("--bulk", action="store_true", help="只查看散装货物车辆")
        parser.add_argument("--container", action="store_true", help="只查看集装箱车辆")
        parser.add_argument("--dangerous", action="store_true", help="只查看危险品车辆")
        parser.add_argument("--refrigerated", action="store_true", help="只查看冷藏车辆")
        parser.add_argument("--carrier", help="按承运商筛选")
        parser.add_argument("--platform", help="按月台筛选")
        parser.add_argument("--export", help="导出JSON报告到指定文件")
        parser.add_argument("--export-csv", dest="export_csv", help="导出CSV明细到指定文件")
        parser.add_argument("--carrier-stats", action="store_true", help="按承运商统计停留时长（基于筛选结果）")
        parser.add_argument("--overtime", action="store_true", help="只查看超时等待车辆")
        parser.add_argument("--threshold", type=int, default=120, help="超时阈值（分钟），默认120分钟")

    def _add_logs_parser(self, subparsers):
        parser = subparsers.add_parser("logs", help="查看操作日志 / 导出交接班日志 / 车辆时间线")
        parser.add_argument("--operator", default=None, help="调度员姓名（同主参数，也用于按调度员筛选日志）")
        parser.add_argument("--limit", type=int, default=50, help="显示最近N条记录，默认50条")
        parser.add_argument("--type", choices=["checkin", "call", "platform", "start", "finish", "delay",
                                               "resume", "cancel", "appointment", "import", "export"],
                            help="按操作类型筛选")
        parser.add_argument("--queue", type=int, help="按排队号筛选")
        parser.add_argument("--plate", help="按车牌号筛选")
        parser.add_argument("--start", dest="start_time", help="开始时间 (如: 2026-06-12 08:00:00)")
        parser.add_argument("--end", dest="end_time", help="结束时间 (如: 2026-06-12 16:00:00)")
        parser.add_argument("--export-shift", dest="export_shift", help="导出交接班日志到指定JSON文件")
        parser.add_argument("--shift", choices=["早班", "中班", "晚班"],
                            help="班次视图：早班(06-14)/中班(14-22)/晚班(22-06)，配合--export-shift使用")
        parser.add_argument("--timeline", help="查看指定车牌的完整时间线（签到→叫号→装卸→完成等）")
        parser.add_argument("--export-timeline", dest="export_timeline",
                            help="导出车辆时间线到指定JSON文件，需配合--timeline使用")

    def _resolve_operator(self, args) -> str:
        sub_op = getattr(args, 'operator', None)
        return sub_op if sub_op else "系统"

    def _parse_cargo_filter(self, args) -> Optional[CargoType]:
        if getattr(args, 'general', False):
            return CargoType.GENERAL
        if getattr(args, 'bulk', False):
            return CargoType.BULK
        if getattr(args, 'container', False):
            return CargoType.CONTAINER
        if getattr(args, 'dangerous', False):
            return CargoType.DANGEROUS
        if getattr(args, 'refrigerated', False):
            return CargoType.REFRIGERATED
        return None

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
            "resume": OperationType.RESUME_QUEUE,
            "cancel": OperationType.CANCEL_QUEUE,
            "appointment": OperationType.CHANGE_APPOINTMENT,
            "import": OperationType.BATCH_IMPORT,
            "export": OperationType.EXPORT_REPORT
        }
        return mapping[op_type]

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
        match_icon = "✓" if suggestion.get("platform_match") else "⚠"
        print(f"\n  建议 {idx + 1}: #{suggestion['queue_number']} {suggestion['plate_number']}")
        print(f"     货类: {suggestion['cargo_type']} | 承运商: {suggestion['carrier']} | 已等待: {suggestion['waiting_minutes']}分钟")
        print(f"     建议月台: {suggestion['suggested_platform'] or '暂无可用月台'} {match_icon}")
        print(f"     推荐理由: {'，'.join(suggestion['reasons'])}")

    def _print_summary(self, vehicles: List[Vehicle], threshold: int = 120, filters: List[str] = None):
        waiting = len([v for v in vehicles if v.status == VehicleStatus.WAITING])
        called = len([v for v in vehicles if v.status == VehicleStatus.CALLED])
        loading = len([v for v in vehicles if v.status == VehicleStatus.LOADING])
        finished = len([v for v in vehicles if v.status == VehicleStatus.FINISHED])
        delayed = len([v for v in vehicles if v.status == VehicleStatus.DELAYED])
        cancelled = len([v for v in vehicles if v.status == VehicleStatus.CANCELLED])
        overtime = len([v for v in vehicles if v.is_overtime(threshold)])
        finished_vehicles = [v for v in vehicles if v.status == VehicleStatus.FINISHED]
        total_stay = sum(v.stay_minutes() or 0 for v in finished_vehicles)
        avg_stay = round(total_stay / len(finished_vehicles), 1) if finished_vehicles else 0

        print("=" * 70)
        if filters:
            print(f"筛选条件: {' | '.join(filters)}")
        print(f"报告日期: {datetime.now().strftime('%Y-%m-%d')}")
        print(f"总车辆数: {len(vehicles)}")
        print(f"等待中: {waiting} | 已叫号: {called} | 装卸中: {loading} | 已完成: {finished} | 延迟: {delayed} | 已取消: {cancelled}")
        print(f"超时等待: {overtime} | 平均停留时长: {avg_stay} 分钟")
        print("=" * 70)

    def cmd_checkin(self, args):
        operator = self._resolve_operator(args)

        if args.import_csv:
            print(f"\n📥 开始CSV预检: {args.import_csv}")
            print("=" * 60)

            preview = self.storage.preview_csv_import(args.import_csv)

            if "error" in preview:
                print(f"❌ {preview['error']}")
                return

            print(f"📋 预检结果：")
            print(f"   ✅ 可导入: {preview['valid']} 辆")
            print(f"   ⏭️  跳过(重复): {preview['skipped']} 辆")
            print(f"   ❌ 格式错误: {preview['errors']} 辆")

            if preview["warnings"]:
                print(f"\n⚠️  预检警告/错误明细：")
                for w in preview["warnings"]:
                    print(f"   - {w}")

            if preview["valid_rows"]:
                print(f"\n📋 待导入车辆预览：")
                for r in preview["valid_rows"]:
                    print(f"   第{r['row_num']}行: {r['plate']} | {r['cargo_type'].value} | {r['carrier']} | {r['appointment']}")

            if preview["error_rows"]:
                failed_file = os.path.splitext(args.import_csv)[0] + "_failed.csv"
                self.storage.export_failed_rows(preview["error_rows"], failed_file)
                print(f"\n📤 错误行已导出到: {failed_file}，请修改后重新导入")

            if preview["valid"] == 0:
                print("\n❌ 没有可导入的有效数据，已取消导入。")
                return

            print(f"\n" + "=" * 60)
            confirm = input(f"确认导入 {preview['valid']} 辆车辆？(y/N): ")
            if confirm.lower() == 'y':
                success, skipped, errors, error_details = self.storage.execute_csv_import(preview, operator=operator)
                print("=" * 60)
                print(f"✅ 导入完成！成功: {success} | 跳过重复: {skipped} | 格式错误: {errors}")
                print("=" * 60)
                if error_details:
                    print("详细信息:")
                    for detail in error_details:
                        print(f"  - {detail}")
                print("=" * 60)
            else:
                print("已取消导入。")
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
        operator = self._resolve_operator(args)

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
                reason = suggestion.get("reason", "没有可调度的车辆")
                print(f"❌ {reason}")
                if "platform_status" in suggestion and suggestion["platform_status"]:
                    print(f"\n📊 当前月台使用情况（全部满载）:")
                    for platform, status in suggestion["platform_status"].items():
                        bar = "█" * status["loading"] + "░" * (status["capacity"] - status["loading"])
                        print(f"   {platform}: {bar} {status['loading']}/{status['capacity']}")
                return

            print(f"📊 当前月台使用情况:")
            for platform, status in suggestion["platform_status"].items():
                bar = "█" * status["loading"] + "░" * status["available"]
                full_tag = " [满]" if status["available"] == 0 else ""
                print(f"   {platform}: {bar} {status['loading']}/{status['capacity']}{full_tag}")

            print(f"\n💡 推荐叫号顺序 (共 {suggestion['total_ready']} 辆待调度):")
            print("-" * 70)
            for i, s in enumerate(suggestion["suggestions"]):
                self._print_suggestion(s, i)

            if suggestion.get("skipped_no_platform", 0) > 0:
                print(f"\n⚠️  另有 {suggestion['skipped_no_platform']} 辆车因月台满载暂无法叫号")

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

        cargo_filter = self._parse_cargo_filter(args)
        if cargo_filter:
            vehicles = [v for v in self.storage.get_waiting_vehicles() if v.cargo_type == cargo_filter]
            print(f"\n📋 {cargo_filter.value}等待车辆列表：")
            self._print_vehicle_table(vehicles, show_details=True)
        elif args.list:
            vehicles = self.storage.get_waiting_vehicles()
            normal = [v for v in vehicles if v.status == VehicleStatus.WAITING]
            delayed = [v for v in vehicles if v.status == VehicleStatus.DELAYED]
            print(f"\n📋 当前等待车辆列表 (正常: {len(normal)}, 延迟: {len(delayed)}):")
            self._print_vehicle_table(vehicles, show_details=True)
            if delayed:
                print(f"\nℹ️  延迟车辆共 {len(delayed)} 辆，批量叫号时默认跳过，使用 --include-delayed 可包含")
                print("   使用 delay --resume 恢复排队，delay --cancel 取消排队")
        elif args.count:
            include_delayed = getattr(args, 'include_delayed', False)
            called = self.storage.call_vehicles(args.count, args.platform, include_delayed=include_delayed, operator=operator)
            if called:
                print(f"\n📢 已叫号 {len(called)} 辆车：")
                for v in called:
                    platform_info = f"，前往月台 {v.platform}" if v.platform else ""
                    print(f"  #{v.queue_number} {v.plate_number} ({v.carrier}){platform_info}")
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
        operator = self._resolve_operator(args)

        if args.resume:
            v = self.storage.resume_queue(args.queue, operator=operator)
            if v:
                print("\n" + "=" * 50)
                print("✅ 恢复排队成功！")
                print("=" * 50)
                print(f"排队号: #{v.queue_number}")
                print(f"车牌号: {v.plate_number}")
                print(f"当前状态: {v.status.value}")
                print(f"操作人: {operator}")
                print("=" * 50)
            else:
                print(f"错误：未找到排队号为 {args.queue} 的延迟车辆")
            return

        if args.cancel:
            v = self.storage.cancel_queue(args.queue, operator=operator)
            if v:
                print("\n" + "=" * 50)
                print("✅ 取消排队成功！")
                print("=" * 50)
                print(f"排队号: #{v.queue_number}")
                print(f"车牌号: {v.plate_number}")
                print(f"当前状态: {v.status.value}")
                print(f"操作人: {operator}")
                print("=" * 50)
            else:
                print(f"错误：未找到排队号为 {args.queue} 的可取消车辆")
            return

        if args.change_appointment:
            new_appt = args.change_appointment
            if len(new_appt) <= 5 and ':' in new_appt:
                today = datetime.now().strftime("%Y-%m-%d")
                new_appt = f"{today} {new_appt}:00"
            v = self.storage.change_appointment(args.queue, new_appt, operator=operator)
            if v:
                print("\n" + "=" * 50)
                print("✅ 修改预约时段成功！")
                print("=" * 50)
                print(f"排队号: #{v.queue_number}")
                print(f"车牌号: {v.plate_number}")
                print(f"新预约时段: {v.appointment_time}")
                print(f"操作人: {operator}")
                print("=" * 50)
            else:
                print(f"错误：未找到排队号为 {args.queue} 的车辆")
            return

        if not args.reason:
            print("错误：标记延迟必须提供 --reason 参数")
            print("或使用 --resume 恢复排队 / --cancel 取消排队 / --change-appointment 修改预约时段")
            sys.exit(1)

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
            print("   使用 delay --resume 恢复排队")
            print("   使用 delay --cancel 取消排队")
            print("   使用 delay --change-appointment 修改预约时段")
        else:
            print(f"错误：未找到排队号为 {args.queue} 的车辆")

    def cmd_finish(self, args):
        operator = self._resolve_operator(args)
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
        operator = self._resolve_operator(args)
        carrier = args.carrier
        platform = args.platform
        cargo_type = self._parse_cargo_filter(args)

        title_parts = []
        if cargo_type:
            title_parts.append(f"{cargo_type.value}车辆")
        if args.overtime:
            title_parts.append(f"超时等待车辆报告 (阈值: {args.threshold}分钟)")
        if not title_parts:
            title_parts.append("今日排队汇总报告")
        print(f"\n📊 {'，'.join(title_parts)}")

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
            self._print_summary(vehicles, args.threshold, filters)
        else:
            report = self.storage.get_daily_report(carrier=carrier, cargo_type=cargo_type, platform=platform)
            vehicles = report.vehicles
            self._print_summary(vehicles, args.threshold, filters)

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
            filepath = self.storage.export_report_json(
                args.export, cargo_type=cargo_type, carrier=carrier, platform=platform, operator=operator
            )
            print(f"\n✅ JSON报告已导出到: {filepath}")

        if args.export_csv:
            filepath = self.storage.export_report_csv(
                args.export_csv, cargo_type=cargo_type, carrier=carrier, platform=platform, operator=operator
            )
            print(f"✅ CSV明细已导出到: {filepath}")

        self.check_overtime_vehicles(args.threshold)

    def cmd_logs(self, args):
        op_type = self._parse_operation_type(args.type) if args.type else None
        queue_number = getattr(args, 'queue', None)
        plate = getattr(args, 'plate', None)
        start_time = getattr(args, 'start_time', None)
        end_time = getattr(args, 'end_time', None)
        logs_operator_filter = getattr(args, 'operator', None)
        shift = getattr(args, 'shift', None)

        timeline_plate = getattr(args, 'timeline', None)
        export_timeline = getattr(args, 'export_timeline', None)
        if timeline_plate:
            tl = self.storage.get_vehicle_timeline(timeline_plate)
            if not tl["found"]:
                print(f"\n❌ 未找到车牌 {timeline_plate} 的车辆记录")
                return

            print(f"\n🕐 车辆时间线：{timeline_plate}")
            print(f"   排队号：#{tl['queue_number']} | 当前状态：{tl['current_status']} | "
                  f"货类：{tl['cargo_type']} | 承运商：{tl['carrier']}")
            print("=" * 80)

            if not tl["timeline"]:
                print("   暂无时间线节点")
            else:
                for i, node in enumerate(tl["timeline"]):
                    connector = "└─" if i == len(tl["timeline"]) - 1 else "├─"
                    platform_info = f" | 月台：{node['platform']}" if node.get("platform") else ""
                    print(f"   {connector} [{node['time']}] {node['event']}{platform_info}")
                    print(f"      操作人：{node['operator']} | {node['description']}")

            print("=" * 80)
            print(f"   共 {len(tl['timeline'])} 个节点")

            if export_timeline:
                operator = self._resolve_operator(args)
                filepath = self.storage.export_vehicle_timeline(export_timeline, timeline_plate, operator=operator)
                print(f"\n✅ 车辆时间线已导出到: {filepath}")
            return

        export_shift = getattr(args, 'export_shift', None)
        export_operator = self._resolve_operator(args)
        if export_shift:
            filepath = self.storage.export_shift_log(
                export_shift, start_time=start_time, end_time=end_time, shift=shift, operator=export_operator
            )
            handover = self.storage.get_shift_handover_data(start_time=start_time, end_time=end_time, shift=shift)
            shift_info = f"（{shift}）" if shift else ""
            print(f"\n✅ 交接班日志{shift_info}已导出到: {filepath}")
            print(f"   时间段: {handover['period']['start']} ~ {handover['period']['end']}")
            print(f"   总车辆数: {handover['total_vehicles']}")
            print(f"   等待中: {handover['summary']['waiting']} | 已叫号: {handover['summary']['called']} | "
                  f"装卸中: {handover['summary']['loading']} | 已完成: {handover['summary']['finished']} | "
                  f"延迟: {handover['summary']['delayed']} | 已取消: {handover['summary']['cancelled']}")

            groups = handover.get("shift_groups", {})
            if groups:
                group_labels = {
                    "pending": "📋 待处理车辆",
                    "called_not_loading": "📢 已叫号未装卸",
                    "delayed_not_resumed": "⏸️  延迟未恢复",
                    "overtime": "⚠️  超时等待",
                }
                for key, label in group_labels.items():
                    items = groups.get(key, [])
                    if items:
                        print(f"\n   {label}（{len(items)}辆）:")
                        for item in items:
                            pn = item.get("plate_number", "?")
                            qn = item.get("queue_number", "?")
                            platform = item.get("platform") or "-"
                            wait = item.get("waiting_minutes")
                            wait_str = f" 已等{wait}分钟" if wait else ""
                            last_change = item.get("last_status_change", "")
                            print(f"     #{qn} {pn} 月台:{platform}{wait_str} [{last_change}]")

            if handover['vehicle_last_status']:
                print(f"\n   车辆最后状态变化（只记录真实状态变更）:")
                for s in handover['vehicle_last_status']:
                    print(f"     #{s['queue_number']} {s['plate_number']}: "
                          f"{s['last_status_change']} → {s['current_status']} "
                          f"({s['last_operator']} @ {s['last_status_change_time']})")
            return

        logs = self.storage.get_logs(
            operator=logs_operator_filter,
            operation_type=op_type,
            queue_number=queue_number,
            plate_number=plate,
            start_time=start_time,
            end_time=end_time
        )
        logs = logs[:args.limit]

        filter_parts = []
        if logs_operator_filter:
            filter_parts.append(f"调度员={logs_operator_filter}")
        if op_type:
            filter_parts.append(f"类型={op_type.value}")
        if queue_number:
            filter_parts.append(f"排队号=#{queue_number}")
        if plate:
            filter_parts.append(f"车牌={plate}")
        if start_time:
            filter_parts.append(f"起始={start_time}")
        if end_time:
            filter_parts.append(f"截止={end_time}")

        print("\n📋 操作日志" + (f"（{' | '.join(filter_parts)}）" if filter_parts else "（最近操作在最前）"))
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
        if args is None:
            args = sys.argv[1:]

        global_operator = None
        remaining_args = []
        i = 0
        while i < len(args):
            a = args[i]
            if a == "--operator" and i + 1 < len(args):
                global_operator = args[i + 1]
                i += 2
            elif a.startswith("--operator="):
                global_operator = a.split("=", 1)[1]
                i += 1
            else:
                remaining_args.append(a)
                i += 1

        parsed_args = self.parser.parse_args(remaining_args)

        sub_operator = getattr(parsed_args, 'operator', None)
        resolved_operator = sub_operator or global_operator or "系统"
        parsed_args.operator = resolved_operator

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
