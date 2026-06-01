"""
工业数据模拟器 — 模拟 CNC 数控机床、环境传感器、产线计数器
通过 MQTT 发布遥测数据，同时提供 REST API 供 Telegraf HTTP 插件拉取
"""

import json
import math
import os
import random
import threading
import time
from datetime import datetime, timezone

import numpy as np
from flask import Flask, jsonify
import paho.mqtt.client as mqtt

# ==================== 配置 ====================
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
HTTP_PORT = int(os.getenv("HTTP_PORT", 5001))

# ==================== 设备定义 ====================
DEVICES = {
    # CNC 数控机床
    "CNC-A01": {
        "device_type": "cnc",
        "workshop": "workshop-1",
        "line": "line-A",
        "metrics": {
            "temperature": {"base": 45, "range": 15, "noise": 2, "unit": "°C"},
            "vibration": {"base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "rpm": {"base": 3000, "range": 2000, "noise": 50, "unit": "rpm"},
            "power": {"base": 4500, "range": 3000, "noise": 200, "unit": "W"},
            "feed_rate": {"base": 1200, "range": 800, "noise": 30, "unit": "mm/min"},
            "voltage": {"base": 380, "range": 10, "noise": 2, "unit": "V"},
            "current": {"base": 12, "range": 8, "noise": 0.5, "unit": "A"},
        },
    },
    "CNC-A02": {
        "device_type": "cnc",
        "workshop": "workshop-1",
        "line": "line-A",
        "metrics": {
            "temperature": {"base": 42, "range": 18, "noise": 2.5, "unit": "°C"},
            "vibration": {"base": 1.2, "range": 2.5, "noise": 0.4, "unit": "mm/s"},
            "rpm": {"base": 3500, "range": 2500, "noise": 80, "unit": "rpm"},
            "power": {"base": 5200, "range": 3500, "noise": 300, "unit": "W"},
            "feed_rate": {"base": 1500, "range": 1000, "noise": 50, "unit": "mm/min"},
            "voltage": {"base": 380, "range": 8, "noise": 1.5, "unit": "V"},
            "current": {"base": 14, "range": 6, "noise": 0.3, "unit": "A"},
        },
    },
    "CNC-B01": {
        "device_type": "cnc",
        "workshop": "workshop-2",
        "line": "line-B",
        "metrics": {
            "temperature": {"base": 50, "range": 20, "noise": 3, "unit": "°C"},
            "vibration": {"base": 2.0, "range": 3.0, "noise": 0.5, "unit": "mm/s"},
            "rpm": {"base": 4000, "range": 3000, "noise": 100, "unit": "rpm"},
            "power": {"base": 6000, "range": 4000, "noise": 400, "unit": "W"},
            "feed_rate": {"base": 1800, "range": 1200, "noise": 60, "unit": "mm/min"},
            "voltage": {"base": 380, "range": 12, "noise": 3, "unit": "V"},
            "current": {"base": 16, "range": 10, "noise": 0.6, "unit": "A"},
        },
    },
    # 环境传感器
    "SENSOR-ENV01": {
        "device_type": "sensor",
        "workshop": "workshop-1",
        "line": "line-A",
        "metrics": {
            "temperature": {"base": 25, "range": 8, "noise": 0.5, "unit": "°C"},
            "humidity": {"base": 55, "range": 20, "noise": 2, "unit": "%"},
            "pressure": {"base": 6.5, "range": 2, "noise": 0.2, "unit": "bar"},
            "flow_rate": {"base": 120, "range": 40, "noise": 5, "unit": "L/min"},
        },
    },
    "SENSOR-ENV02": {
        "device_type": "sensor",
        "workshop": "workshop-2",
        "line": "line-B",
        "metrics": {
            "temperature": {"base": 28, "range": 10, "noise": 0.8, "unit": "°C"},
            "humidity": {"base": 60, "range": 25, "noise": 3, "unit": "%"},
            "pressure": {"base": 7.0, "range": 3, "noise": 0.3, "unit": "bar"},
            "flow_rate": {"base": 150, "range": 50, "noise": 8, "unit": "L/min"},
        },
    },
    # 产线 PLC
    "PLC-LINE-A": {
        "device_type": "plc",
        "workshop": "workshop-1",
        "line": "line-A",
        "metrics": {
            "count": {"base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 2},
            "defect_count": {"base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 0.08},
            "quality_rate": {"base": 96, "range": 4, "noise": 0.5, "unit": "%"},
            "oee": {"base": 85, "range": 15, "noise": 2, "unit": "%"},
            "cycle_time": {"base": 30, "range": 10, "noise": 1, "unit": "s"},
        },
    },
    "PLC-LINE-B": {
        "device_type": "plc",
        "workshop": "workshop-2",
        "line": "line-B",
        "metrics": {
            "count": {"base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 1.5},
            "defect_count": {"base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 0.12},
            "quality_rate": {"base": 94, "range": 6, "noise": 0.8, "unit": "%"},
            "oee": {"base": 82, "range": 18, "noise": 3, "unit": "%"},
            "cycle_time": {"base": 35, "range": 12, "noise": 2, "unit": "s"},
        },
    },
}

# ==================== 数据生成引擎 ====================

class IndustrialDataEngine:
    """基于正弦波 + 噪声的工业数据生成器"""

    def __init__(self):
        self.t = 0
        self.accumulators = {}
        # 初始化累加器
        for dev_id, dev in DEVICES.items():
            for metric_name, metric in dev["metrics"].items():
                if metric.get("accumulator"):
                    key = f"{dev_id}.{metric_name}"
                    self.accumulators[key] = metric["base"]

    def generate(self, device_id: str, metric_name: str, metric_config: dict) -> float:
        """生成单个指标数据，模拟真实工业场景"""
        self.t += 0.01
        key = f"{device_id}.{metric_name}"

        # 累加器类型（产量计数）
        if metric_config.get("accumulator"):
            rate = metric_config["rate"]
            # 随机波动生产速率
            rate *= random.uniform(0.8, 1.2)
            self.accumulators[key] += rate
            return round(self.accumulators[key])

        base = metric_config["base"]
        rng = metric_config["range"]
        noise = metric_config["noise"]

        # 正弦波模拟周期性变化（如设备启停周期）
        cycle = math.sin(self.t * 0.1 + hash(device_id) % 100) * rng * 0.3

        # 缓慢漂移（模拟设备老化/环境变化）
        drift = math.sin(self.t * 0.01 + hash(metric_name) % 50) * rng * 0.15

        # 高斯噪声
        gaussian_noise = np.random.normal(0, noise)

        # 偶发异常脉冲（5% 概率）
        spike = 0
        if random.random() < 0.05:
            spike = random.uniform(-rng * 0.4, rng * 0.4)

        value = base + cycle + drift + gaussian_noise + spike

        # 确保物理合理性
        if metric_name in ["rpm", "power", "count", "defect_count"]:
            value = max(0, value)
        if metric_name == "humidity":
            value = max(0, min(100, value))
        if metric_name in ["quality_rate", "oee"]:
            value = max(0, min(100, value))

        return round(value, 2)


engine = IndustrialDataEngine()

# ==================== MQTT 发布器 ====================

def mqtt_publisher():
    """每 3 秒向 MQTT 发布所有设备数据"""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="industrial-simulator")

    def on_connect(c, userdata, flags, reason_code, properties):
        print(f"[MQTT] 已连接到 {MQTT_HOST}:{MQTT_PORT}, reason_code={reason_code}")

    def on_disconnect(c, userdata, flags, reason_code, properties):
        print(f"[MQTT] 断开连接, reason_code={reason_code}")

    def on_publish(c, userdata, mid, reason_code, properties):
        pass

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    connected = False
    while not connected:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_start()
            connected = True
            print(f"[MQTT] 连接中... {MQTT_HOST}:{MQTT_PORT}")
        except Exception as e:
            print(f"[MQTT] 连接失败，3秒后重试: {e}")
            time.sleep(3)

    while True:
        try:
            for dev_id, dev in DEVICES.items():
                topic_prefix = f"factory/{dev['device_type']}/{dev_id}"
                payload = {
                    "machine_id": dev_id,
                    "device_type": dev["device_type"],
                    "workshop": dev["workshop"],
                    "line": dev["line"],
                    "status": random.choice(["running", "running", "running", "running", "idle", "warning"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                for metric_name, metric_cfg in dev["metrics"].items():
                    payload[metric_name] = engine.generate(dev_id, metric_name, metric_cfg)

                result = client.publish(topic_prefix, json.dumps(payload), qos=1)
                
            time.sleep(3)
        except Exception as e:
            print(f"[MQTT] 发布错误: {e}")
            time.sleep(5)


# ==================== HTTP REST API ====================

app = Flask(__name__)

@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Telegraf HTTP 插件拉取接口"""
    results = []
    for dev_id, dev in DEVICES.items():
        row = {
            "machine_id": dev_id,
            "device_type": dev["device_type"],
            "workshop": dev["workshop"],
            "line": dev["line"],
            "status": "running",
        }
        for metric_name, metric_cfg in dev["metrics"].items():
            row[metric_name] = engine.generate(dev_id, metric_name, metric_cfg)
        results.append(row)
    return jsonify(results)


@app.route("/api/devices", methods=["GET"])
def get_devices():
    """返回设备列表"""
    devices = []
    for dev_id, dev in DEVICES.items():
        devices.append({
            "id": dev_id,
            "type": dev["device_type"],
            "workshop": dev["workshop"],
            "line": dev["line"],
            "metrics": list(dev["metrics"].keys()),
        })
    return jsonify(devices)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


# ==================== 启动 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("  🏭 工业数据模拟器启动")
    print(f"  MQTT: {MQTT_HOST}:{MQTT_PORT}")
    print(f"  HTTP: http://0.0.0.0:{HTTP_PORT}/api/metrics")
    print(f"  设备数量: {len(DEVICES)}")
    print("=" * 60)

    # 启动 MQTT 发布线程
    mqtt_thread = threading.Thread(target=mqtt_publisher, daemon=True)
    mqtt_thread.start()

    # 启动 HTTP 服务
    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False)