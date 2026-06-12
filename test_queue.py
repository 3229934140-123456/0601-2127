#!/usr/bin/env python3
"""公路运输装卸排队系统测试脚本"""

import os
import sys
import json
import shutil
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Vehicle, CargoType, VehicleStatus, DelayReason
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
