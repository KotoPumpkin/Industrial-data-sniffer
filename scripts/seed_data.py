"""
测试数据注入脚本 — 向 InfluxDB 写入 48 小时工业模拟数据
用法: python scripts/seed_data.py [--url http://localhost:8086] [--hours 48]
"""

import csv
import io
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

# ── 配置 ──────────────────────────────────────────────
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-admin-token-2024")
ORG = os.getenv("INFLUXDB_ORG", "industrial")
BUCKET = os.getenv("INFLUXDB_BUCKET", "factory")
HOURS = 48
INTERVAL_SEC = 30  # 每 30 秒一个数据点

# ── 设备定义 ──────────────────────────────────────────
DEVICES = {
    "CNC-001": {
        "device_type": "cnc", "workshop": "A", "line": "L1",
        "fields": {
            "temperature": (35, 80, 65),
            "vibration": (0.5, 8.0, 3.5),
            "rpm": (1000, 12000, 6000),
            "feed_rate": (50, 500, 200),
        },
    },
    "CNC-002": {
        "device_type": "cnc", "workshop": "A", "line": "L2",
        "fields": {
            "temperature": (38, 85, 70),
            "vibration": (0.3, 6.0, 2.8),
            "rpm": (1500, 10000, 5500),
            "feed_rate": (80, 450, 250),
        },
    },
    "SENSOR-001": {
        "device_type": "sensor", "workshop": "A", "line": "L1",
        "fields": {
            "temperature": (18, 42, 26),
            "humidity": (30, 85, 55),
            "pressure": (95, 115, 101.3),
        },
    },
    "SENSOR-002": {
        "device_type": "sensor", "workshop": "B", "line": "L1",
        "fields": {
            "temperature": (20, 38, 24),
            "humidity": (35, 75, 50),
            "pressure": (98, 112, 101.0),
        },
    },
    "PLC-001": {
        "device_type": "plc", "workshop": "B", "line": "L1",
        "fields": {
            "voltage": (210, 250, 220),
            "current": (5, 45, 18),
            "power": (1000, 9000, 3800),
        },
    },
    "LINE-001": {
        "device_type": "production_line", "workshop": "A", "line": "L1",
        "fields": {
            "count": (0, 60, 25),
            "defect_count": (0, 5, 1),
            "flow_rate": (10, 100, 45),
        },
    },
}


def generate_value(min_v, max_v, base, t, anomaly_prob=0.03):
    """生成带周期性波动 + 噪声的模拟值"""
    # 正弦周期 (模拟日间/夜间工作模式)
    cycle = math.sin(2 * math.pi * t / (24 * 3600)) * 0.15
    # 噪声
    noise = random.gauss(0, (max_v - min_v) * 0.04)
    value = base * (1 + cycle) + noise
    # 异常尖峰
    if random.random() < anomaly_prob:
        value = base + random.choice([-1, 1]) * (max_v - min_v) * random.uniform(0.3, 0.7)
    return round(max(min_v, min(max_v, value)), 2)


def build_line_protocol(device_id, device_info, ts_ns):
    """构建 InfluxDB 行协议数据"""
    tags = f"machine_id={device_id},workshop={device_info['workshop']},line={device_info['line']},device_type={device_info['device_type']}"
    lines = []
    t_offset = ts_ns / 1e9  # 用于周期计算
    for field_name, (min_v, max_v, base) in device_info["fields"].items():
        value = generate_value(min_v, max_v, base, t_offset)
        line = f"industrial_metrics,{tags} {field_name}={value} {ts_ns}"
        lines.append(line)
    return lines


def write_batch(lines):
    """向 InfluxDB 写入一批数据"""
    resp = requests.post(
        f"{INFLUXDB_URL}/api/v2/write",
        params={"org": ORG, "bucket": BUCKET, "precision": "ns"},
        headers={"Authorization": f"Token {TOKEN}", "Content-Type": "text/plain; charset=utf-8"},
        data="\n".join(lines),
    )
    if resp.status_code not in (200, 204):
        print(f"  ✗ 写入失败 [{resp.status_code}]: {resp.text[:200]}")
        return False
    return True


def main():
    # 解析命令行参数
    url = INFLUXDB_URL
    hours = HOURS
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--url" and i < len(sys.argv) - 1:
            url = sys.argv[i + 1]
        elif arg == "--hours" and i < len(sys.argv) - 1:
            hours = int(sys.argv[i + 1])

    print(f"═══════════════════════════════════════════")
    print(f"  工业数据测试数据注入")
    print(f"  InfluxDB: {url}")
    print(f"  时间范围: 最近 {hours} 小时")
    print(f"  数据间隔: {INTERVAL_SEC} 秒")
    print(f"  设备数量: {len(DEVICES)}")
    print(f"═══════════════════════════════════════════")

    # 检查 InfluxDB 连接
    try:
        resp = requests.get(f"{url}/health", timeout=5)
        print(f"  InfluxDB 状态: {resp.status_code} ✓")
    except Exception as e:
        print(f"  ✗ 无法连接 InfluxDB: {e}")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    total_points = int(hours * 3600 / INTERVAL_SEC) * len(DEVICES)
    total_batches = int(hours * 3600 / INTERVAL_SEC)

    print(f"  预计数据点: {total_points}")
    print(f"───────────────────────────────────────────")

    batch_size = 200  # 每 200 个时间点写一次
    written = 0
    ts = start

    for batch_idx in range(total_batches):
        lines = []
        ts_ns = int(ts.timestamp() * 1e9)
        for device_id, device_info in DEVICES.items():
            lines.extend(build_line_protocol(device_id, device_info, ts_ns))

        if write_batch(lines):
            written += len(lines)

        ts += timedelta(seconds=INTERVAL_SEC)

        if (batch_idx + 1) % 200 == 0:
            pct = min((batch_idx + 1) / total_batches * 100, 100)
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"  [{bar}] {pct:.0f}%  ({written} 数据点)")

    print(f"───────────────────────────────────────────")
    print(f"  ✓ 完成! 共写入 {written} 个数据点")
    print(f"  时间范围: {start.strftime('%Y-%m-%d %H:%M')} → {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"═══════════════════════════════════════════")


if __name__ == "__main__":
    main()