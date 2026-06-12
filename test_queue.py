#!/usr/bin/env python3
"""公路运输装卸排队系统测试脚本"""

import os
import sys
import json
import csv
import shutil
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Vehicle, CargoType, VehicleStatus, DelayReason, OperationLog, OperationType, PLATFORM_CARGO_FIT
from storage import QueueStorage


def test_data_directory():
    print("🧪 测试1: 数据目录创建...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)
    assert os.path.exists(test_dir), "数据目录未创建"
    assert os.path.exists(storage._get_today_file()), "今日数据文件未创建"
    print("✅ 数据目录创建测试通过")


def test_vehicle_checkin():
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
    print("\n🧪 测试5: 月台调整...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    v = storage.set_platform(3, "B2")
    assert v is not None, "应找到车辆"
    assert v.platform == "B2", f"月台应为B2，实际为{v.platform}"

    print("✅ 月台调整测试通过")


def test_start_and_finish():
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
    print("\n🧪 测试10: 报表导出...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    storage = QueueStorage(test_dir)

    export_file = os.path.join(test_dir, "export_test.json")
    filepath = storage.export_report_json(export_file)
    assert os.path.exists(filepath), "导出文件未创建"

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert "summary" in data, "导出数据应包含summary"
    assert "vehicles" in data, "导出数据应包含vehicles"
    assert len(data["vehicles"]) >= 4, "导出车辆数应>=4"

    export_dangerous = os.path.join(test_dir, "export_dangerous.json")
    filepath = storage.export_report_json(export_dangerous, CargoType.DANGEROUS)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert len(data["vehicles"]) == 1, "危险品导出应只有1辆车"

    print("✅ 报表导出测试通过")


def test_cli_help():
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
    print("\n🧪 测试15: CSV批量导入（预检+执行）...")
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

    preview = storage.preview_csv_import(csv_file)
    assert preview["valid"] == 4, f"预检有效行应为4，实际为{preview['valid']}"
    assert preview["skipped"] == 1, f"预检跳过应为1，实际为{preview['skipped']}"
    assert preview["errors"] == 2, f"预检错误应为2，实际为{preview['errors']}"
    assert len(preview["valid_rows"]) == 4
    assert len(preview["error_rows"]) == 2

    success, skipped, errors, details = storage.execute_csv_import(preview, operator="导入员")
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

    failed_file = os.path.join(test_dir, "test_import_failed.csv")
    if preview["error_rows"]:
        storage.export_failed_rows(preview["error_rows"], failed_file)
        assert os.path.exists(failed_file), "失败行文件应被创建"
        with open(failed_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2, f"失败行应为2，实际为{len(rows)}"

    print("✅ CSV批量导入测试通过")


def test_dispatch_suggestion():
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
    assert first["suggested_platform"].startswith("C"), "危险品应优先分配C区月台"

    second = suggestion["suggestions"][1]
    assert second["cargo_type"] == "冷藏货物"
    assert second["suggested_platform"].startswith("B"), "冷藏应优先分配B区月台"

    for s in suggestion["suggestions"]:
        assert "queue_number" in s
        assert "plate_number" in s
        assert "reasons" in s
        assert len(s["reasons"]) >= 3
        assert "platform_match" in s

    print("✅ 调度建议功能测试通过")


def test_combined_filters():
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
    filepath = storage.export_report_json(export_file, carrier="顺丰", platform="A1")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert data["filters"]["carrier"] == "顺丰"
    assert data["filters"]["platform"] == "A1"
    assert len(data["vehicles"]) == 1

    print("✅ 组合筛选功能测试通过")


def test_operator_parameter():
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
    storage.export_report_json(os.path.join(test_dir, "test.json"), operator="赵六")

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
    assert len(lisi_logs) == 3

    print("✅ 调度员参数关联测试通过")


def test_delay_resume_cancel():
    print("\n🧪 测试19: 延迟车辆恢复排队/取消排队/改预约...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    for i in range(3):
        v = Vehicle(
            plate_number=f"京W{i+1:05d}",
            driver_phone=f"1390000000{i+1}",
            cargo_type=CargoType.GENERAL,
            carrier="测试物流",
            appointment_time="2026-06-12 10:00:00"
        )
        storage.add_vehicle(v, operator="调度员A")

    storage.mark_delay(2, DelayReason.LATE_ARRIVAL, "堵车", operator="调度员A")
    v = storage.get_vehicle_by_queue(2)
    assert v.status == VehicleStatus.DELAYED

    v_resumed = storage.resume_queue(2, operator="调度员B")
    assert v_resumed is not None
    assert v_resumed.status == VehicleStatus.WAITING
    assert v_resumed.delay_reason is None
    assert v_resumed.delay_time is None

    resume_logs = storage.get_logs(operation_type=OperationType.RESUME_QUEUE)
    assert len(resume_logs) == 1
    assert resume_logs[0].operator == "调度员B"
    assert "恢复" in resume_logs[0].description

    storage.mark_delay(3, DelayReason.CARRIER_REQUEST, "承运商要求", operator="调度员A")
    v_cancelled = storage.cancel_queue(3, operator="调度员C")
    assert v_cancelled is not None
    assert v_cancelled.status == VehicleStatus.CANCELLED

    cancel_logs = storage.get_logs(operation_type=OperationType.CANCEL_QUEUE)
    assert len(cancel_logs) == 1
    assert cancel_logs[0].operator == "调度员C"

    storage.change_appointment(1, "2026-06-12 14:00:00", operator="调度员D")
    v_changed = storage.get_vehicle_by_queue(1)
    assert v_changed.appointment_time == "2026-06-12 14:00:00"

    appt_logs = storage.get_logs(operation_type=OperationType.CHANGE_APPOINTMENT)
    assert len(appt_logs) == 1
    assert appt_logs[0].operator == "调度员D"
    assert "预约时段" in appt_logs[0].description

    print("✅ 延迟车辆恢复/取消/改预约测试通过")


def test_log_advanced_query():
    print("\n🧪 测试20: 操作日志高级查询...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    v1 = Vehicle(plate_number="京X00001", driver_phone="13800000001",
                 cargo_type=CargoType.GENERAL, carrier="物流A", appointment_time="2026-06-12 08:00:00")
    v2 = Vehicle(plate_number="京X00002", driver_phone="13800000002",
                 cargo_type=CargoType.DANGEROUS, carrier="物流B", appointment_time="2026-06-12 09:00:00",
                 dangerous_level="一级")
    storage.add_vehicle(v1, operator="早班A")
    storage.add_vehicle(v2, operator="早班B")

    logs_by_queue = storage.get_logs(queue_number=1)
    assert all(l.queue_number == 1 for l in logs_by_queue)

    logs_by_plate = storage.get_logs(plate_number="京X00002")
    assert all(l.plate_number == "京X00002" for l in logs_by_plate)
    assert len(logs_by_plate) >= 1

    now_str = datetime.now().strftime("%Y-%m-%d")
    logs_by_time = storage.get_logs(start_time=f"{now_str} 00:00:00", end_time=f"{now_str} 23:59:59")
    assert len(logs_by_time) >= 2

    print("✅ 操作日志高级查询测试通过")


def test_shift_handover():
    print("\n🧪 测试21: 交接班日志导出...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    for i in range(3):
        v = Vehicle(plate_number=f"京Y{i+1:05d}", driver_phone=f"1380000000{i+1}",
                     cargo_type=CargoType.GENERAL, carrier="测试物流", appointment_time="2026-06-12 10:00:00")
        storage.add_vehicle(v, operator="交接班测试")

    storage.call_specific_vehicles([1], platform="A1", operator="交接班测试")

    handover = storage.get_shift_handover_data()
    assert "summary" in handover
    assert "vehicle_last_status" in handover
    assert handover["total_vehicles"] == 3
    assert len(handover["vehicle_last_status"]) == 3

    first_vs = handover["vehicle_last_status"][0]
    assert first_vs["queue_number"] == 1
    assert first_vs["current_status"] == "已叫号"
    assert first_vs["last_operator"] == "交接班测试"

    export_file = os.path.join(test_dir, "shift_log.json")
    filepath = storage.export_shift_log(export_file, operator="接班调度")
    assert os.path.exists(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert "summary" in data
    assert "vehicle_last_status" in data
    assert "period" in data

    print("✅ 交接班日志导出测试通过")


def test_report_csv_export():
    print("\n🧪 测试22: 报表CSV明细导出...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    for i in range(3):
        v = Vehicle(plate_number=f"京Z{i+1:05d}", driver_phone=f"1380000000{i+1}",
                     cargo_type=CargoType.GENERAL, carrier=f"物流{i+1}", appointment_time="2026-06-12 10:00:00")
        storage.add_vehicle(v)
        storage.call_specific_vehicles([v.queue_number], platform="A1")
        storage.start_loading(v.queue_number)
        storage.finish_loading(v.queue_number)

    csv_file = os.path.join(test_dir, "report.csv")
    filepath = storage.export_report_csv(csv_file)
    assert os.path.exists(filepath)

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    assert len(rows) == 4, f"CSV应有1行表头+3行数据，实际为{len(rows)}"
    assert "排队号" in rows[0][0]
    assert "车牌号" in rows[0][1]

    filtered_csv = os.path.join(test_dir, "filtered_report.csv")
    storage.export_report_csv(filtered_csv, carrier="物流1")
    with open(filtered_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    assert len(rows) == 2, f"筛选后CSV应有1行表头+1行数据，实际为{len(rows)}"

    print("✅ 报表CSV明细导出测试通过")


def test_dispatch_platform_full():
    print("\n🧪 测试23: 调度建议月台满载检测...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    for i in range(18):
        v = Vehicle(plate_number=f"京F{i+1:05d}", driver_phone=f"1380000000{i+1}",
                     cargo_type=CargoType.GENERAL, carrier="测试物流", appointment_time="2026-06-12 10:00:00")
        v = storage.add_vehicle(v)

    platforms = ["A1"] * 3 + ["A2"] * 3 + ["B1"] * 2 + ["B2"] * 2 + ["C1"] * 4 + ["C2"] * 4
    for i, v in enumerate(storage.get_all_vehicles()):
        if i < len(platforms):
            v.status = VehicleStatus.LOADING
            v.platform = platforms[i]
            v.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            storage.update_vehicle(v)

    v_wait = Vehicle(plate_number="京F99999", driver_phone="13899999999",
                     cargo_type=CargoType.GENERAL, carrier="等待物流", appointment_time="2026-06-12 10:00:00")
    storage.add_vehicle(v_wait)

    suggestion = storage.get_dispatch_suggestion(count=1)
    assert len(suggestion["suggestions"]) == 0, "月台满载时不应有建议"
    assert suggestion.get("reason") == "所有月台已满，无法叫号"

    print("✅ 调度建议月台满载检测测试通过")


def test_cargo_filter_summary():
    print("\n🧪 测试24: 货类筛选汇总统计...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    cargo_types = [CargoType.GENERAL, CargoType.DANGEROUS, CargoType.REFRIGERATED,
                   CargoType.GENERAL, CargoType.DANGEROUS]
    carriers = ["顺丰", "圆通", "京东", "中通", "申通"]

    for i in range(5):
        v = Vehicle(plate_number=f"京G{i+1:05d}", driver_phone=f"1380000000{i+1}",
                     cargo_type=cargo_types[i], carrier=carriers[i],
                     appointment_time="2026-06-12 10:00:00",
                     dangerous_level="一级" if cargo_types[i] == CargoType.DANGEROUS else None,
                     temperature_required="-18°C" if cargo_types[i] == CargoType.REFRIGERATED else None)
        storage.add_vehicle(v)

    storage.call_specific_vehicles([1], platform="A1")
    storage.start_loading(1)
    storage.finish_loading(1)
    storage.mark_delay(2, DelayReason.LATE_ARRIVAL)

    report = storage.get_daily_report(cargo_type=CargoType.DANGEROUS)
    assert report.total_vehicles == 2
    assert report.delayed_count == 1

    summary = storage._compute_vehicle_summary(report.vehicles)
    assert summary["delayed"] == 1
    assert summary["waiting"] + summary["loading"] + summary["finished"] + summary["delayed"] + summary["cancelled"] == 2

    print("✅ 货类筛选汇总统计测试通过")


def test_csv_preview_validation():
    print("\n🧪 测试25: CSV预检数据验证...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    csv_content = """plate,phone,cargo,carrier,appointment,dangerous_level,temperature
京H11111,13500135000,普通货物,中通物流,08:30,,
京H22222,1340bad,危险品,圆通物流,09:00,二级,
京H33333,13300133000,冷藏货物,京东物流,not_a_time,,-18°C
京H44444,13200132000,未知货类,中远海运,10:00,,
京H55555,13100131000,危险品,顺丰物流,11:00,,
"""
    csv_file = os.path.join(test_dir, "test_validation.csv")
    with open(csv_file, 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)

    preview = storage.preview_csv_import(csv_file)
    assert preview["valid"] == 1, f"有效行应为1（仅京H11111），实际为{preview['valid']}"
    assert preview["errors"] >= 3, f"错误行应>=3，实际为{preview['errors']}"

    has_phone_warning = any("电话" in w for w in preview["warnings"])
    assert has_phone_warning, "应检测到电话格式问题"

    has_time_warning = any("预约时间" in w for w in preview["warnings"])
    assert has_time_warning, "应检测到预约时间格式问题"

    print("✅ CSV预检数据验证测试通过")


def test_operator_position():
    print("\n🧪 测试26: --operator 位置灵活识别（子命令前后均可）...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    from queue_cli import QueueCLI
    cli = QueueCLI()
    cli.storage = QueueStorage(test_dir)

    cli.run([
        "--operator", "主调度",
        "checkin",
        "--plate", "京X11111", "--phone", "13500135000",
        "--cargo", "general", "--carrier", "测试承运",
        "--appointment", "09:00"
    ])
    v_main = cli.storage.get_vehicle_by_queue(1)
    assert v_main is not None, "主命令后--operator签到失败"

    logs_main = cli.storage.get_logs(plate_number="京X11111")
    assert len(logs_main) >= 1, "主命令--operator应有日志"
    assert logs_main[0].operator == "主调度", f"主命令operator应为'主调度'，实际{logs_main[0].operator}"

    cli.run([
        "checkin",
        "--plate", "京X22222", "--phone", "13500135001",
        "--cargo", "bulk", "--carrier", "测试承运",
        "--appointment", "10:00",
        "--operator", "子调度"
    ])
    v_sub = cli.storage.get_vehicle_by_queue(2)
    assert v_sub is not None, "子命令后--operator签到失败"

    logs_sub = cli.storage.get_logs(plate_number="京X22222")
    assert len(logs_sub) >= 1, "子命令--operator应有日志"
    assert logs_sub[0].operator == "子调度", f"子命令operator应为'子调度'，实际{logs_sub[0].operator}"

    cli.run([
        "checkin",
        "--plate", "京X33333", "--phone", "13500135002",
        "--cargo", "container", "--carrier", "测试承运",
        "--appointment", "11:00"
    ])
    logs_none = cli.storage.get_logs(plate_number="京X33333")
    assert len(logs_none) >= 1, "无operator签到应有日志"
    assert logs_none[0].operator == "系统", f"默认operator应为'系统'，实际{logs_none[0].operator}"

    cli.run([
        "--operator", "主优先",
        "delay",
        "--queue", "1", "--reason", "late",
        "--operator", "子优先"
    ])
    logs_prio = cli.storage.get_logs(queue_number=1, operation_type=OperationType.MARK_DELAY)
    assert len(logs_prio) >= 1, "子命令--operator优先未生效"
    assert logs_prio[0].operator == "子优先", f"子命令--operator优先应为'子优先'，实际{logs_prio[0].operator}"

    print("✅ --operator 位置灵活识别测试通过")


def test_csv_dangerous_temperature_validation():
    print("\n🧪 测试27: CSV预检危险品等级和冷藏温度格式校验...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir, exist_ok=True)
    storage = QueueStorage(test_dir)

    csv_path = os.path.join(test_dir, "bad_cargo_fields.csv")
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(["plate", "phone", "cargo", "carrier", "appointment", "dangerous_level", "temperature"])
        w.writerow(["京D11111", "13800138000", "危险品", "圆通A", "09:00", "甲级", ""])
        w.writerow(["京D22222", "13800138001", "危险品", "圆通B", "09:30", "乱填等级", ""])
        w.writerow(["京D33333", "13800138002", "危险品", "圆通C", "10:00", "X99", ""])
        w.writerow(["京D44444", "13800138003", "冷藏货物", "京东A", "10:30", "", "-18℃"])
        w.writerow(["京D55555", "13800138004", "冷藏货物", "京东B", "11:00", "", "明显不对的温度"])
        w.writerow(["京D66666", "13800138005", "冷藏货物", "京东C", "11:30", "", "2~8度"])
        w.writerow(["京D77777", "13800138006", "危险品", "圆通D", "12:00", "3类", ""])
        w.writerow(["京D88888", "13800138007", "冷藏货物", "京东D", "12:30", "", "冷冻"])
        w.writerow(["京D99999", "13800138008", "普通货物", "中通D", "13:00", "", ""])

    preview = storage.preview_csv_import(csv_path)

    has_bad_dangerous = any("乱填等级" in w and "危险品等级" in w for w in preview["warnings"])
    assert has_bad_dangerous, "应检测到'乱填等级'为无效危险品等级"

    has_x99_dangerous = any("X99" in w and "危险品等级" in w for w in preview["warnings"])
    assert has_x99_dangerous, "应检测到'X99'为无效危险品等级"

    has_bad_temp = any("明显不对的温度" in w and "冷藏温度" in w for w in preview["warnings"])
    assert has_bad_temp, "应检测到'明显不对的温度'为无效冷藏温度"

    valid_plates = [r["plate"] for r in preview["valid_rows"]]
    assert "京D22222" not in valid_plates, "危险品乱填等级不应进入有效行"
    assert "京D33333" not in valid_plates, "危险品X99不应进入有效行"
    assert "京D55555" not in valid_plates, "冷藏明显不对温度不应进入有效行"
    assert "京D11111" in valid_plates, "危险品甲级应为有效"
    assert "京D44444" in valid_plates, "冷藏-18℃应为有效"
    assert "京D66666" in valid_plates, "冷藏2~8度应为有效"
    assert "京D77777" in valid_plates, "危险品3类应为有效"
    assert "京D88888" in valid_plates, "冷藏冷冻应为有效"
    assert "京D99999" in valid_plates, "普通货物应为有效"

    assert preview["errors"] >= 3, f"至少应有3个错误行，实际{preview['errors']}"

    failed_file = os.path.join(test_dir, "bad_cargo_fields_failed.csv")
    storage.export_failed_rows(preview["error_rows"], failed_file)
    assert os.path.exists(failed_file), "失败行文件未生成"

    with open(failed_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        failed_rows = list(reader)
    assert len(failed_rows) >= 3, f"失败文件应至少3行，实际{len(failed_rows)}"
    plates_failed = [r['plate'] for r in failed_rows]
    assert "京D22222" in plates_failed or "京D33333" in plates_failed, "失败文件应包含乱填等级/无效等级车辆"

    print("✅ CSV危险品等级和冷藏温度校验测试通过")


def test_shift_handover_status_change_only():
    print("\n🧪 测试28: 交接班日志只追踪真实状态变化（排除改预约/月台调整）...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    v1 = Vehicle(plate_number="京Z11111", driver_phone="13600136000",
                 cargo_type=CargoType.GENERAL, carrier="承运A",
                 appointment_time="2026-06-12 09:00:00")
    v1 = storage.add_vehicle(v1, operator="调度A")

    storage.call_specific_vehicles([1], platform="A1", operator="调度B")
    storage.set_platform(1, "A2", operator="调度B")
    storage.change_appointment(1, "2026-06-12 14:00:00", operator="调度C")

    handover = storage.get_shift_handover_data()
    v1_status = next((s for s in handover["vehicle_last_status"] if s["queue_number"] == 1), None)
    assert v1_status is not None, "车辆1应有最后状态记录"
    assert v1_status["last_status_change"] == OperationType.CALL.value, \
        f"最后状态变化应为'叫号'（排除改预约/月台调整），实际{v1_status['last_status_change']}"
    assert v1_status["last_operator"] == "调度B", \
        f"最后状态变化操作人应为'调度B'，实际{v1_status['last_operator']}"
    assert "last_status_change_detail" in v1_status, "应有状态变更详情字段"
    assert v1_status["current_status"] == VehicleStatus.CALLED.value

    v2 = Vehicle(plate_number="京Z22222", driver_phone="13600136001",
                 cargo_type=CargoType.DANGEROUS, carrier="承运B",
                 appointment_time="2026-06-12 10:00:00", dangerous_level="3类")
    v2 = storage.add_vehicle(v2, operator="调度A")
    storage.mark_delay(2, DelayReason.LATE_ARRIVAL, note="堵车", operator="调度D")
    storage.change_appointment(2, "2026-06-12 16:00:00", operator="调度E")

    handover2 = storage.get_shift_handover_data()
    v2_status = next((s for s in handover2["vehicle_last_status"] if s["queue_number"] == 2), None)
    assert v2_status is not None, "车辆2应有最后状态记录"
    assert v2_status["last_status_change"] == OperationType.MARK_DELAY.value, \
        f"车辆2最后状态变化应为'标记延迟'，实际{v2_status['last_status_change']}"
    assert v2_status["last_operator"] == "调度D", \
        f"车辆2最后状态操作人应为'调度D'，实际{v2_status['last_operator']}"

    print("✅ 交接班日志只追踪真实状态变化测试通过")


def test_call_per_vehicle_logs():
    print("\n🧪 测试29: 批量/建议叫号每辆车有独立日志，可按车牌追溯...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    plates = ["京Y11111", "京Y22222", "京Y33333", "京Y44444", "京Y55555"]
    for i, p in enumerate(plates, start=1):
        v = Vehicle(plate_number=p, driver_phone=f"137001370{i:02d}",
                    cargo_type=CargoType.GENERAL, carrier="承运商批量",
                    appointment_time=f"2026-06-12 0{i}:00:00")
        storage.add_vehicle(v, operator="调度一")

    storage.call_vehicles(3, platform="A1", operator="调度二")

    for p in plates[:3]:
        logs_p = storage.get_logs(plate_number=p)
        call_logs = [l for l in logs_p if l.operation_type == OperationType.CALL]
        assert len(call_logs) >= 1, f"车牌{p}按车牌查不到叫号日志"
        assert call_logs[0].plate_number == p, f"车牌{p}的叫号日志plate_number字段缺失"
        assert call_logs[0].operator == "调度二", f"车牌{p}叫号操作人错误"
        assert call_logs[0].queue_number is not None, f"车牌{p}叫号日志排队号缺失"

    storage.call_specific_vehicles([4, 5], platform="A2", operator="调度三")
    for p in plates[3:]:
        logs_p = storage.get_logs(plate_number=p, operation_type=OperationType.CALL)
        assert len(logs_p) >= 1, f"指定叫号车牌{p}按车牌查不到叫号日志"
        assert logs_p[0].operator == "调度三", f"指定叫号车牌{p}操作人错误"

    logs_count = len(storage.get_logs(operation_type=OperationType.CALL))
    assert logs_count >= 7, f"应有>=7条叫号日志（2聚合+5单车），实际{logs_count}"

    print("✅ 批量/指定叫号每辆车独立日志测试通过")


def test_all_cargo_type_report_filters():
    print("\n🧪 测试30: 所有5种货类筛选报表与导出（general/bulk/container等）...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    storage = QueueStorage(test_dir)

    cargo_specs = [
        ("京T11111", CargoType.GENERAL, "承运G", "09:00"),
        ("京T22222", CargoType.GENERAL, "承运G", "09:30"),
        ("京T33333", CargoType.BULK, "承运B", "10:00"),
        ("京T44444", CargoType.CONTAINER, "承运C", "10:30"),
        ("京T55555", CargoType.DANGEROUS, "承运D", "11:00"),
        ("京T66666", CargoType.REFRIGERATED, "承运R", "11:30"),
    ]
    for idx, (p, ct, car, appt) in enumerate(cargo_specs, start=1):
        kwargs = {}
        if ct == CargoType.DANGEROUS:
            kwargs["dangerous_level"] = "3类"
        if ct == CargoType.REFRIGERATED:
            kwargs["temperature_required"] = "-18℃"
        v = Vehicle(plate_number=p, driver_phone=f"139001390{idx:02d}",
                    cargo_type=ct, carrier=car,
                    appointment_time=f"2026-06-12 {appt}:00", **kwargs)
        storage.add_vehicle(v, operator=f"调度{idx}")

    storage.call_specific_vehicles([1], operator="调度X")
    storage.call_specific_vehicles([3], operator="调度X")
    storage.start_loading(1, operator="调度Y")
    storage.finish_loading(1, operator="调度Y")
    storage.mark_delay(5, DelayReason.LATE_ARRIVAL, operator="调度Z")

    for ct, expected_count, label in [
        (CargoType.GENERAL, 2, "普通货物"),
        (CargoType.BULK, 1, "散装货物"),
        (CargoType.CONTAINER, 1, "集装箱"),
        (CargoType.DANGEROUS, 1, "危险品"),
        (CargoType.REFRIGERATED, 1, "冷藏货物"),
    ]:
        rep = storage.get_daily_report(cargo_type=ct)
        assert len(rep.vehicles) == expected_count, \
            f"{label}筛选应返回{expected_count}辆，实际{len(rep.vehicles)}"
        s = storage._compute_vehicle_summary(rep.vehicles)
        for k in ("waiting", "called", "loading", "finished", "delayed", "cancelled",
                  "overtime", "avg_stay_minutes"):
            assert k in s, f"{label}汇总缺少键{k}"

    json_path = os.path.join(test_dir, "bulk_report.json")
    csv_path = os.path.join(test_dir, "container_report.csv")
    storage.export_report_json(json_path, cargo_type=CargoType.BULK, operator="调度E")
    storage.export_report_csv(csv_path, cargo_type=CargoType.CONTAINER, operator="调度F")

    assert os.path.exists(json_path), "散装JSON报告未生成"
    with open(json_path, 'r', encoding='utf-8') as f:
        jr = json.load(f)
    assert jr["filters"]["cargo_type"] == CargoType.BULK.value, "JSON筛选货类不正确"
    assert "summary" in jr and jr["summary"]["called"] == 1, "JSON汇总called数量应为1"
    assert len(jr["vehicles"]) == 1

    assert os.path.exists(csv_path), "集装箱CSV报告未生成"
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        csv_rows = list(reader)
    assert len(csv_rows) == 2, f"CSV应包含1表头+1数据共2行，实际{len(csv_rows)}"
    assert "货类" in csv_rows[0], "CSV表头缺少'货类'列"
    assert "京T44444" in csv_rows[1], "CSV明细缺少集装箱车辆"

    from queue_cli import QueueCLI
    cli = QueueCLI()
    cli.storage = storage
    cli.run(["report", "--general"])
    cli.run(["report", "--bulk"])
    cli.run(["report", "--container"])
    cli.run(["call", "--list", "--general"])
    cli.run(["call", "--list", "--bulk"])
    cli.run(["call", "--list", "--container"])

    print("✅ 所有5种货类筛选报表和导出测试通过")


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
        test_delay_resume_cancel,
        test_log_advanced_query,
        test_shift_handover,
        test_report_csv_export,
        test_dispatch_platform_full,
        test_cargo_filter_summary,
        test_csv_preview_validation,
        test_operator_position,
        test_csv_dangerous_temperature_validation,
        test_shift_handover_status_change_only,
        test_call_per_vehicle_logs,
        test_all_cargo_type_report_filters,
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
            import traceback
            traceback.print_exc()
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
