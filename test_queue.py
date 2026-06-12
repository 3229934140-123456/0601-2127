#!/usr/bin/env python3
"""公路运输装卸排队系统测试脚本"""

import os
import sys
import json
import shutil
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Vehicle, CargoType, VehicleStatus, DelayReason, OperationLog, OperationType
from storage import QueueStorage


def test_data_directory():
    """测试数据目录创建"""
    print("🧪 测试1: 数据目录创建...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)
    assert os.path.exists(test_dir), "数据目录未创建"
    assert os.path.exists(storage._get_today_file()), "今日数据文件未创建"
    print("✅ 数据目录创建测试通过")


def test_vehicle_checkin():
    """测试车辆签到"""
    print("\n🧪 测试2: 车辆签到...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    v1 = Vehicle(
        plate_number="京A12345",
        driver_phone="13800138000",
        cargo_type=CargoType.GENERAL,
        carrier="顺丰物流",
        appointment_time="2026-06-12 09:00:00"
    )
    v1 = storage.add_vehicle(v1)
    assert v1.queue_number == 1, f"排队号应为1，实际为{v1.queue_number}"
    assert v1.status == VehicleStatus.WAITING, "状态应为等待中"

    v2 = Vehicle(
        plate_number="京B67890",
        driver_phone="13900139000",
        cargo_type=CargoType.DANGEROUS,
        carrier="圆通物流",
        appointment_time="2026-06-12 10:00:00",
        dangerous_level="三级"
    )
    v2 = storage.add_vehicle(v2)
    assert v2.queue_number == 2, f"排队号应为2，实际为{v2.queue_number}"

    v3 = Vehicle(
        plate_number="京C11111",
        driver_phone="13700137000",
        cargo_type=CargoType.REFRIGERATED,
        carrier="京东物流",
        appointment_time="2026-06-12 11:00:00",
        temperature_required="-18°C"
    )
    v3 = storage.add_vehicle(v3)
    assert v3.queue_number == 3, f"排队号应为3，实际为{v3.queue_number}"

    vehicles = storage.get_all_vehicles()
    assert len(vehicles) == 3, f"车辆数应为3，实际为{len(vehicles)}"

    print("✅ 车辆签到测试通过")


def test_waiting_and_call():
    """测试等待队列和叫号"""
    print("\n🧪 测试3: 等待队列和叫号...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    waiting = storage.get_waiting_vehicles()
    assert len(waiting) == 3, f"等待车辆应为3，实际为{len(waiting)}"

    called = storage.call_vehicles(2, platform="A1")
    assert len(called) == 2, f"应叫号2辆，实际为{len(called)}"
    assert called[0].queue_number == 1, "第一辆叫号应为#1"
    assert called[0].status == VehicleStatus.CALLED, "状态应为已叫号"
    assert called[0].platform == "A1", "月台应为A1"

    waiting = storage.get_waiting_vehicles()
    assert len(waiting) == 1, f"等待车辆应为1，实际为{len(waiting)}"

    print("✅ 等待队列和叫号测试通过")


def test_delay():
    """测试延迟标记"""
    print("\n🧪 测试4: 延迟标记...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    v = storage.mark_delay(3, DelayReason.LATE_ARRIVAL, "司机堵车")
    assert v is not None, "应找到车辆"
    assert v.status == VehicleStatus.DELAYED, "状态应为延迟"
    assert v.delay_reason == DelayReason.LATE_ARRIVAL, "延迟原因应为迟到"
    assert v.delay_note == "司机堵车", "备注不匹配"

    waiting = storage.get_waiting_vehicles()
    assert len(waiting) == 1, f"等待车辆应为1（含延迟），实际为{len(waiting)}"
    assert waiting[0].status == VehicleStatus.DELAYED, "延迟车辆应在等待队列末尾"

    print("✅ 延迟标记测试通过")


def test_platform_adjustment():
    """测试月台调整"""
    print("\n🧪 测试5: 月台调整...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    v = storage.set_platform(3, "B2")
    assert v is not None, "应找到车辆"
    assert v.platform == "B2", f"月台应为B2，实际为{v.platform}"

    print("✅ 月台调整测试通过")


def test_start_and_finish():
    """测试装卸开始和完成"""
    print("\n🧪 测试6: 装卸开始和完成...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    v_start = storage.start_loading(1)
    assert v_start is not None, "应找到车辆"
    assert v_start.status == VehicleStatus.LOADING, "状态应为装卸中"
    assert v_start.start_time is not None, "开始时间应已设置"

    v_finish = storage.finish_loading(1)
    assert v_finish is not None, "应找到车辆"
    assert v_finish.status == VehicleStatus.FINISHED, "状态应为已完成"
    assert v_finish.finish_time is not None, "完成时间应已设置"
    assert v_finish.stay_minutes() is not None, "应能计算停留时长"

    print("✅ 装卸开始和完成测试通过")


def test_specific_cargo_filter():
    """测试危险品/冷藏车筛选"""
    print("\n🧪 测试7: 危险品/冷藏车筛选...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    dangerous = storage.get_dangerous_vehicles()
    assert len(dangerous) == 1, f"危险品车辆应为1，实际为{len(dangerous)}"
    assert dangerous[0].cargo_type == CargoType.DANGEROUS

    refrigerated = storage.get_refrigerated_vehicles()
    assert len(refrigerated) == 1, f"冷藏车辆应为1，实际为{len(refrigerated)}"
    assert refrigerated[0].cargo_type == CargoType.REFRIGERATED

    print("✅ 危险品/冷藏车筛选测试通过")


def test_overtime_detection():
    """测试超时检测"""
    print("\n🧪 测试8: 超时检测...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    overtime_vehicle = Vehicle(
        plate_number="京D99999",
        driver_phone="13600136000",
        cargo_type=CargoType.GENERAL,
        carrier="韵达物流",
        appointment_time="2026-06-12 08:00:00"
    )
    overtime_vehicle.checkin_time = (datetime.now() - timedelta(minutes=150)).strftime("%Y-%m-%d %H:%M:%S")
    overtime_vehicle = storage.add_vehicle(overtime_vehicle)

    overtime = storage.get_overtime_vehicles(120)
    assert len(overtime) >= 1, "应检测到超时车辆"
    assert overtime_vehicle.is_overtime(120) == True, "车辆应标记为超时"

    finished_v = storage.get_vehicle_by_queue(1)
    assert finished_v.is_overtime(120) == False, "已完成车辆不应标记为超时"

    print("✅ 超时检测测试通过")


def test_carrier_stats():
    """测试承运商统计"""
    print("\n🧪 测试9: 承运商统计...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    stats = storage.get_carrier_stats()
    assert len(stats) >= 3, f"承运商数应>=3，实际为{len(stats)}"

    sf_stats = next((s for s in stats if s["carrier"] == "顺丰物流"), None)
    assert sf_stats is not None, "应找到顺丰物流统计"
    assert sf_stats["total"] == 1, "顺丰物流总车辆应为1"
    assert sf_stats["finished"] == 1, "顺丰物流已完成应为1"
    assert sf_stats["avg_stay_minutes"] >= 0, "平均停留时长应>=0"

    print("✅ 承运商统计测试通过")


def test_export_report():
    """测试报表导出"""
    print("\n🧪 测试10: 报表导出...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    export_file = os.path.join(test_dir, "export_test.json")
    filepath = storage.export_report(export_file)
    assert os.path.exists(filepath), "导出文件未创建"

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert "summary" in data, "导出数据应包含summary"
    assert "vehicles" in data, "导出数据应包含vehicles"
    assert len(data["vehicles"]) >= 4, "导出车辆数应>=4"

    export_dangerous = os.path.join(test_dir, "export_dangerous.json")
    filepath = storage.export_report(export_dangerous, CargoType.DANGEROUS)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert len(data["vehicles"]) == 1, "危险品导出应只有1辆车"

    print("✅ 报表导出测试通过")


def test_cli_help():
    """测试CLI帮助"""
    print("\n🧪 测试11: CLI帮助...")
    import subprocess
    result = subprocess.run([sys.executable, "queue_cli.py", "--help"],
                          capture_output=True, text=True, cwd=os.path.dirname(__file__))
    assert result.returncode == 0, "帮助命令执行失败"
    assert "checkin" in result.stdout, "帮助应包含checkin"
    assert "call" in result.stdout, "帮助应包含call"
    assert "delay" in result.stdout, "帮助应包含delay"
    assert "finish" in result.stdout, "帮助应包含finish"
    assert "report" in result.stdout, "帮助应包含report"
    print("✅ CLI帮助测试通过")


def test_data_persistence():
    """测试数据持久化"""
    print("\n🧪 测试12: 数据持久化...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage1 = QueueStorage(test_dir)
    vehicles1 = storage1.get_all_vehicles()
    count1 = len(vehicles1)

    storage2 = QueueStorage(test_dir)
    vehicles2 = storage2.get_all_vehicles()
    count2 = len(vehicles2)

    assert count1 == count2, "两次读取数据量不一致"
    assert vehicles1[0].plate_number == vehicles2[0].plate_number, "数据内容不一致"

    print("✅ 数据持久化测试通过")


def test_delayed_vehicle_skipping():
    """测试批量叫号时跳过延迟车辆"""
    print("\n🧪 测试13: 延迟车辆跳过逻辑...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    for i in range(5):
        v = Vehicle(
            plate_number=f"京T{i+1:05d}",
            driver_phone=f"1380000000{i+1}",
            cargo_type=CargoType.GENERAL,
            carrier="测试物流",
            appointment_time="2026-06-12 10:00:00"
        )
        storage.add_vehicle(v)

    storage.mark_delay(2, DelayReason.LATE_ARRIVAL, "测试延迟")
    storage.mark_delay(4, DelayReason.DOCUMENT_ISSUE, "测试延迟2")

    ready = storage.get_ready_vehicles()
    assert len(ready) == 3, f"正常等待车辆应为3，实际为{len(ready)}"
    assert ready[0].queue_number == 1
    assert ready[1].queue_number == 3
    assert ready[2].queue_number == 5

    called = storage.call_vehicles(5)
    assert len(called) == 3, f"应只叫号3辆正常车，实际为{len(called)}"
    assert called[0].queue_number == 1
    assert called[1].queue_number == 3
    assert called[2].queue_number == 5

    called_with_delayed = storage.call_vehicles(5, include_delayed=True)
    assert len(called_with_delayed) == 2, f"应叫号2辆延迟车，实际为{len(called_with_delayed)}"

    print("✅ 延迟车辆跳过逻辑测试通过")


def test_operation_logs():
    """测试操作日志功能"""
    print("\n🧪 测试14: 操作日志功能...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    v = Vehicle(
        plate_number="京L00001",
        driver_phone="13900000001",
        cargo_type=CargoType.GENERAL,
        carrier="测试物流",
        appointment_time="2026-06-12 10:00:00"
    )
    v = storage.add_vehicle(v, operator="测试员")

    storage.call_specific_vehicles([1], platform="A1", operator="测试员")
    storage.set_platform(1, "A2", operator="测试员")
    storage.start_loading(1, operator="测试员")
    storage.finish_loading(1, operator="测试员")

    all_logs = storage.get_logs()
    assert len(all_logs) >= 5, f"应至少有5条日志，实际为{len(all_logs)}"

    checkin_logs = storage.get_logs(operation_type=OperationType.CHECKIN)
    assert len(checkin_logs) == 1, f"应1条签到日志，实际为{len(checkin_logs)}"
    assert checkin_logs[0].operator == "测试员"

    operator_logs = storage.get_logs(operator="测试员")
    assert len(operator_logs) >= 5, f"测试员的日志应>=5，实际为{len(operator_logs)}"

    call_logs = storage.get_logs(operation_type=OperationType.CALL)
    assert len(call_logs) >= 1

    for log in all_logs:
        assert log.timestamp is not None
        assert log.operation_type is not None
        assert log.description is not None

    print("✅ 操作日志功能测试通过")


def test_csv_import():
    """测试CSV批量导入"""
    print("\n🧪 测试15: CSV批量导入...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    csv_content = """plate,phone,cargo,carrier,appointment,dangerous_level,temperature
京M11111,13500135000,普通货物,中通物流,08:30,,
京N22222,13400134000,危险品,圆通物流,09:00,二级,
京P33333,13300133000,冷藏货物,京东物流,09:30,,-18°C
京Q44444,13200132000,集装箱,中远海运,10:00,,
京M11111,13500135000,普通货物,中通物流,08:30,,
,13100131000,普通货物,顺丰物流,10:30,,
京R55555,13000130000,危险品,申通物流,11:00,,
"""
    csv_file = os.path.join(test_dir, "test_import.csv")
    with open(csv_file, 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)

    success, skipped, errors, details = storage.import_from_csv(csv_file, operator="导入员")
    assert success == 4, f"成功导入应为4，实际为{success}"
    assert skipped == 1, f"跳过重复应为1，实际为{skipped}"
    assert errors == 2, f"错误应为2，实际为{errors}"

    vehicles = storage.get_all_vehicles()
    assert len(vehicles) == 4, f"总车辆应为4，实际为{len(vehicles)}"

    plates = {v.plate_number for v in vehicles}
    assert "京M11111" in plates
    assert "京N22222" in plates
    assert "京P33333" in plates
    assert "京Q44444" in plates

    dangerous = storage.get_dangerous_vehicles()
    assert len(dangerous) == 1
    assert dangerous[0].dangerous_level == "二级"

    refrigerated = storage.get_refrigerated_vehicles()
    assert len(refrigerated) == 1
    assert refrigerated[0].temperature_required == "-18°C"

    import_logs = storage.get_logs(operation_type=OperationType.BATCH_IMPORT)
    assert len(import_logs) == 1
    assert import_logs[0].operator == "导入员"

    print("✅ CSV批量导入测试通过")


def test_dispatch_suggestion():
    """测试调度建议功能"""
    print("\n🧪 测试16: 调度建议功能...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    now = datetime.now()
    past_appt = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    far_past_appt = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    future_appt = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    vehicles_data = [
        ("京S11111", CargoType.GENERAL, "物流A", past_appt),
        ("京S22222", CargoType.DANGEROUS, "物流B", far_past_appt),
        ("京S33333", CargoType.REFRIGERATED, "物流C", past_appt),
        ("京S44444", CargoType.GENERAL, "物流D", future_appt),
        ("京S55555", CargoType.CONTAINER, "物流E", past_appt),
    ]

    for plate, cargo, carrier, appt in vehicles_data:
        v = Vehicle(
            plate_number=plate,
            driver_phone="13800000000",
            cargo_type=cargo,
            carrier=carrier,
            appointment_time=appt,
            dangerous_level="一级" if cargo == CargoType.DANGEROUS else None,
            temperature_required="-18°C" if cargo == CargoType.REFRIGERATED else None
        )
        storage.add_vehicle(v)

    suggestion = storage.get_dispatch_suggestion(count=3)
    assert "suggestions" in suggestion
    assert len(suggestion["suggestions"]) == 3
    assert "platform_status" in suggestion
    assert "total_ready" in suggestion

    first = suggestion["suggestions"][0]
    assert first["cargo_type"] == "危险品"
    assert first["suggested_platform"] is not None

    for s in suggestion["suggestions"]:
        assert "queue_number" in s
        assert "plate_number" in s
        assert "reasons" in s
        assert len(s["reasons"]) >= 2

    print("✅ 调度建议功能测试通过")


def test_combined_filters():
    """测试组合筛选功能"""
    print("\n🧪 测试17: 组合筛选功能...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    carriers = ["顺丰", "圆通", "京东", "顺丰", "圆通"]
    cargo_types = [CargoType.GENERAL, CargoType.DANGEROUS, CargoType.REFRIGERATED, CargoType.GENERAL, CargoType.DANGEROUS]
    platforms = ["A1", "A1", "B1", "B1", "A1"]

    for i in range(5):
        v = Vehicle(
            plate_number=f"京U{i+1:05d}",
            driver_phone=f"1380000000{i+1}",
            cargo_type=cargo_types[i],
            carrier=carriers[i],
            appointment_time="2026-06-12 10:00:00",
            dangerous_level="一级" if cargo_types[i] == CargoType.DANGEROUS else None,
            temperature_required="-18°C" if cargo_types[i] == CargoType.REFRIGERATED else None
        )
        v = storage.add_vehicle(v)
        v.platform = platforms[i]
        storage.update_vehicle(v)
        if i < 3:
            storage.call_specific_vehicles([v.queue_number], platform=platforms[i])
            storage.start_loading(v.queue_number)
            storage.finish_loading(v.queue_number)

    sf_vehicles = storage.filter_vehicles(carrier="顺丰")
    assert len(sf_vehicles) == 2

    a1_vehicles = storage.filter_vehicles(platform="A1")
    assert len(a1_vehicles) == 3

    sf_a1_vehicles = storage.filter_vehicles(carrier="顺丰", platform="A1")
    assert len(sf_a1_vehicles) == 1

    dangerous_a1 = storage.filter_vehicles(cargo_type=CargoType.DANGEROUS, platform="A1")
    assert len(dangerous_a1) == 2

    report = storage.get_daily_report(carrier="顺丰", platform="A1")
    assert report.total_vehicles == 1
    assert len(report.vehicles) == 1

    carrier_stats = storage.get_carrier_stats(sf_vehicles)
    assert len(carrier_stats) == 1
    assert carrier_stats[0]["carrier"] == "顺丰"
    assert carrier_stats[0]["total"] == 2

    export_file = os.path.join(test_dir, "filtered_export.json")
    filepath = storage.export_report(export_file, carrier="顺丰", platform="A1")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert data["filters"]["carrier"] == "顺丰"
    assert data["filters"]["platform"] == "A1"
    assert len(data["vehicles"]) == 1
    assert data["summary"]["total_vehicles"] == 1

    print("✅ 组合筛选功能测试通过")


def test_operator_parameter():
    """测试调度员参数关联"""
    print("\n🧪 测试18: 调度员参数关联...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    v = Vehicle(
        plate_number="京V00001",
        driver_phone="13800000000",
        cargo_type=CargoType.GENERAL,
        carrier="测试物流",
        appointment_time="2026-06-12 10:00:00"
    )
    storage.add_vehicle(v, operator="张三")

    storage.call_specific_vehicles([1], platform="A1", operator="李四")
    storage.set_platform(1, "A2", operator="李四")
    storage.start_loading(1, operator="王五")
    storage.finish_loading(1, operator="王五")
    storage.export_report(os.path.join(test_dir, "test.json"), operator="赵六")

    logs = storage.get_logs()
    operators = {log.operator for log in logs}

    assert "张三" in operators
    assert "李四" in operators
    assert "王五" in operators
    assert "赵六" in operators

    zhangsan_logs = storage.get_logs(operator="张三")
    assert len(zhangsan_logs) == 1
    assert zhangsan_logs[0].operation_type == OperationType.CHECKIN

    lisi_logs = storage.get_logs(operator="李四")
    assert len(lisi_logs) == 2

    print("✅ 调度员参数关联测试通过")


def main():
    print("=" * 60)
    print("开始公路运输装卸排队系统测试")
    print("=" * 60)

    tests = [
        test_data_directory,
        test_vehicle_checkin,
        test_waiting_and_call,
        test_delay,
        test_platform_adjustment,
        test_start_and_finish,
        test_specific_cargo_filter,
        test_overtime_detection,
        test_carrier_stats,
        test_export_report,
        test_cli_help,
        test_data_persistence,
        test_delayed_vehicle_skipping,
        test_operation_logs,
        test_csv_import,
        test_dispatch_suggestion,
        test_combined_filters,
        test_operator_parameter,
    ]

    passed = 0
    failed = 0
    failed_tests = []

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} 失败: {e}")
            failed += 1
            failed_tests.append(test.__name__)
        except Exception as e:
            print(f"❌ {test.__name__} 异常: {e}")
            failed += 1
            failed_tests.append(test.__name__)

    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    if failed_tests:
        print(f"失败的测试: {', '.join(failed_tests)}")
    print("=" * 60)

    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
