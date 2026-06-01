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
# 结构: 设备 → 点位(points) → 指标数据 + 设备级聚合统计(stats)
DEVICES = {
    # ===== 车间1：广东深圳 =====
    "CNC-A01": {
        "device_type": "cnc",
        "workshop": "workshop-1",
        "line": "line-A",
        "points": {
            "CNC-A01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴前轴承温度", "base": 46, "range": 14, "noise": 1.8, "unit": "°C"},
            "CNC-A01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴后轴承温度", "base": 43, "range": 12, "noise": 1.5, "unit": "°C"},
            "CNC-A01_motor_winding_temp": {"metric": "temperature", "label": "电机绕组温度", "base": 48, "range": 16, "noise": 2.2, "unit": "°C"},
            "CNC-A01_vibration": {"metric": "vibration", "label": "主轴振动", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-A01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3000, "range": 2000, "noise": 50, "unit": "rpm"},
            "CNC-A01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 3000, "noise": 200, "unit": "W"},
            "CNC-A01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 1200, "range": 800, "noise": 30, "unit": "mm/min"},
            "CNC-A01_voltage": {"metric": "voltage", "label": "电源电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-A01_current": {"metric": "current", "label": "工作电流", "base": 12, "range": 8, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-A02": {
        "device_type": "cnc",
        "workshop": "workshop-1",
        "line": "line-A",
        "points": {
            "CNC-A02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴前轴承温度", "base": 42, "range": 16, "noise": 2.2, "unit": "°C"},
            "CNC-A02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴后轴承温度", "base": 40, "range": 14, "noise": 2.0, "unit": "°C"},
            "CNC-A02_motor_winding_temp": {"metric": "temperature", "label": "电机绕组温度", "base": 45, "range": 18, "noise": 2.8, "unit": "°C"},
            "CNC-A02_vibration": {"metric": "vibration", "label": "主轴振动", "base": 1.2, "range": 2.5, "noise": 0.4, "unit": "mm/s"},
            "CNC-A02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 2500, "noise": 80, "unit": "rpm"},
            "CNC-A02_power": {"metric": "power", "label": "功率消耗", "base": 5200, "range": 3500, "noise": 300, "unit": "W"},
            "CNC-A02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 1500, "range": 1000, "noise": 50, "unit": "mm/min"},
            "CNC-A02_voltage": {"metric": "voltage", "label": "电源电压", "base": 380, "range": 8, "noise": 1.5, "unit": "V"},
            "CNC-A02_current": {"metric": "current", "label": "工作电流", "base": 14, "range": 6, "noise": 0.3, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-B01": {
        "device_type": "cnc",
        "workshop": "workshop-2",
        "line": "line-B",
        "points": {
            "CNC-B01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴前轴承温度", "base": 50, "range": 18, "noise": 2.5, "unit": "°C"},
            "CNC-B01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴后轴承温度", "base": 47, "range": 16, "noise": 2.8, "unit": "°C"},
            "CNC-B01_motor_winding_temp": {"metric": "temperature", "label": "电机绕组温度", "base": 53, "range": 22, "noise": 3.2, "unit": "°C"},
            "CNC-B01_vibration": {"metric": "vibration", "label": "主轴振动", "base": 2.0, "range": 3.0, "noise": 0.5, "unit": "mm/s"},
            "CNC-B01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 4000, "range": 3000, "noise": 100, "unit": "rpm"},
            "CNC-B01_power": {"metric": "power", "label": "功率消耗", "base": 6000, "range": 4000, "noise": 400, "unit": "W"},
            "CNC-B01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 1800, "range": 1200, "noise": 60, "unit": "mm/min"},
            "CNC-B01_voltage": {"metric": "voltage", "label": "电源电压", "base": 380, "range": 12, "noise": 3, "unit": "V"},
            "CNC-B01_current": {"metric": "current", "label": "工作电流", "base": 16, "range": 10, "noise": 0.6, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    # 环境传感器
    "SENSOR-ENV01": {
        "device_type": "sensor",
        "workshop": "workshop-1",
        "line": "line-A",
        "points": {
            "SENSOR-ENV01_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 8, "noise": 0.5, "unit": "°C"},
            "SENSOR-ENV01_humidity": {"metric": "humidity", "label": "相对湿度", "base": 55, "range": 20, "noise": 2, "unit": "%"},
            "SENSOR-ENV01_pressure": {"metric": "pressure", "label": "大气压力", "base": 6.5, "range": 2, "noise": 0.2, "unit": "bar"},
            "SENSOR-ENV01_flow_rate": {"metric": "flow_rate", "label": "冷却液流量", "base": 120, "range": 40, "noise": 5, "unit": "L/min"},
        },
    },
    "SENSOR-ENV02": {
        "device_type": "sensor",
        "workshop": "workshop-2",
        "line": "line-B",
        "points": {
            "SENSOR-ENV02_temperature": {"metric": "temperature", "label": "环境温度", "base": 28, "range": 10, "noise": 0.8, "unit": "°C"},
            "SENSOR-ENV02_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 25, "noise": 3, "unit": "%"},
            "SENSOR-ENV02_pressure": {"metric": "pressure", "label": "大气压力", "base": 7.0, "range": 3, "noise": 0.3, "unit": "bar"},
            "SENSOR-ENV02_flow_rate": {"metric": "flow_rate", "label": "冷却液流量", "base": 150, "range": 50, "noise": 8, "unit": "L/min"},
        },
    },
    # 产线 PLC
    "PLC-LINE-A": {
        "device_type": "plc",
        "workshop": "workshop-1",
        "line": "line-A",
        "points": {
            "PLC-LINE-A_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 2},
            "PLC-LINE-A_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 0.08},
            "PLC-LINE-A_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 96, "range": 4, "noise": 0.5, "unit": "%"},
            "PLC-LINE-A_oee": {"metric": "oee", "label": "设备综合效率(OEE)", "base": 85, "range": 15, "noise": 2, "unit": "%"},
            "PLC-LINE-A_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 30, "range": 10, "noise": 1, "unit": "s"},
        },
    },
    "PLC-LINE-B": {
        "device_type": "plc",
        "workshop": "workshop-2",
        "line": "line-B",
        "points": {
            "PLC-LINE-B_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 1.5},
            "PLC-LINE-B_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 0.12},
            "PLC-LINE-B_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 94, "range": 6, "noise": 0.8, "unit": "%"},
            "PLC-LINE-B_oee": {"metric": "oee", "label": "设备综合效率(OEE)", "base": 82, "range": 18, "noise": 3, "unit": "%"},
            "PLC-LINE-B_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 35, "range": 12, "noise": 2, "unit": "s"},
        },
    },
    # ===== 车间3：山东青岛 =====
    "CNC-C01": {
        "device_type": "cnc",
        "workshop": "workshop-3",
        "line": "line-C",
        "points": {
            "CNC-C01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴前轴承温度", "base": 48, "range": 15, "noise": 2.2, "unit": "°C"},
            "CNC-C01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴后轴承温度", "base": 46, "range": 14, "noise": 2.0, "unit": "°C"},
            "CNC-C01_motor_winding_temp": {"metric": "temperature", "label": "电机绕组温度", "base": 50, "range": 18, "noise": 2.8, "unit": "°C"},
            "CNC-C01_vibration": {"metric": "vibration", "label": "主轴振动", "base": 1.8, "range": 2.2, "noise": 0.4, "unit": "mm/s"},
            "CNC-C01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3200, "range": 2200, "noise": 70, "unit": "rpm"},
            "CNC-C01_power": {"metric": "power", "label": "功率消耗", "base": 4800, "range": 3200, "noise": 250, "unit": "W"},
            "CNC-C01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 1300, "range": 900, "noise": 40, "unit": "mm/min"},
            "CNC-C01_voltage": {"metric": "voltage", "label": "电源电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-C01_current": {"metric": "current", "label": "工作电流", "base": 13, "range": 7, "noise": 0.4, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-C02": {
        "device_type": "cnc",
        "workshop": "workshop-3",
        "line": "line-C",
        "points": {
            "CNC-C02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴前轴承温度", "base": 44, "range": 13, "noise": 1.8, "unit": "°C"},
            "CNC-C02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴后轴承温度", "base": 42, "range": 12, "noise": 1.6, "unit": "°C"},
            "CNC-C02_motor_winding_temp": {"metric": "temperature", "label": "电机绕组温度", "base": 46, "range": 16, "noise": 2.2, "unit": "°C"},
            "CNC-C02_vibration": {"metric": "vibration", "label": "主轴振动", "base": 1.4, "range": 1.8, "noise": 0.3, "unit": "mm/s"},
            "CNC-C02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 2800, "range": 1800, "noise": 60, "unit": "rpm"},
            "CNC-C02_power": {"metric": "power", "label": "功率消耗", "base": 4200, "range": 2800, "noise": 200, "unit": "W"},
            "CNC-C02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 1100, "range": 700, "noise": 30, "unit": "mm/min"},
            "CNC-C02_voltage": {"metric": "voltage", "label": "电源电压", "base": 380, "range": 8, "noise": 1.5, "unit": "V"},
            "CNC-C02_current": {"metric": "current", "label": "工作电流", "base": 11, "range": 5, "noise": 0.3, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-ENV03": {
        "device_type": "sensor",
        "workshop": "workshop-3",
        "line": "line-C",
        "points": {
            "SENSOR-ENV03_temperature": {"metric": "temperature", "label": "环境温度", "base": 22, "range": 10, "noise": 0.6, "unit": "°C"},
            "SENSOR-ENV03_humidity": {"metric": "humidity", "label": "相对湿度", "base": 58, "range": 22, "noise": 2.5, "unit": "%"},
            "SENSOR-ENV03_pressure": {"metric": "pressure", "label": "大气压力", "base": 6.8, "range": 2.5, "noise": 0.25, "unit": "bar"},
            "SENSOR-ENV03_flow_rate": {"metric": "flow_rate", "label": "冷却液流量", "base": 100, "range": 35, "noise": 4, "unit": "L/min"},
        },
    },
    "PLC-LINE-C": {
        "device_type": "plc",
        "workshop": "workshop-3",
        "line": "line-C",
        "points": {
            "PLC-LINE-C_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 1.8},
            "PLC-LINE-C_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 0.10},
            "PLC-LINE-C_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 95, "range": 5, "noise": 0.6, "unit": "%"},
            "PLC-LINE-C_oee": {"metric": "oee", "label": "设备综合效率(OEE)", "base": 87, "range": 13, "noise": 2, "unit": "%"},
            "PLC-LINE-C_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 28, "range": 8, "noise": 1, "unit": "s"},
        },
    },
    # ===== 车间4：浙江杭州 =====
    "CNC-D01": {
        "device_type": "cnc",
        "workshop": "workshop-4",
        "line": "line-D",
        "points": {
            "CNC-D01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴前轴承温度", "base": 47, "range": 16, "noise": 2.0, "unit": "°C"},
            "CNC-D01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴后轴承温度", "base": 44, "range": 15, "noise": 1.8, "unit": "°C"},
            "CNC-D01_motor_winding_temp": {"metric": "temperature", "label": "电机绕组温度", "base": 49, "range": 18, "noise": 2.5, "unit": "°C"},
            "CNC-D01_vibration": {"metric": "vibration", "label": "主轴振动", "base": 1.6, "range": 2.0, "noise": 0.35, "unit": "mm/s"},
            "CNC-D01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3600, "range": 2400, "noise": 90, "unit": "rpm"},
            "CNC-D01_power": {"metric": "power", "label": "功率消耗", "base": 5500, "range": 3800, "noise": 350, "unit": "W"},
            "CNC-D01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 1600, "range": 1100, "noise": 55, "unit": "mm/min"},
            "CNC-D01_voltage": {"metric": "voltage", "label": "电源电压", "base": 380, "range": 9, "noise": 1.8, "unit": "V"},
            "CNC-D01_current": {"metric": "current", "label": "工作电流", "base": 15, "range": 9, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-ENV04": {
        "device_type": "sensor",
        "workshop": "workshop-4",
        "line": "line-D",
        "points": {
            "SENSOR-ENV04_temperature": {"metric": "temperature", "label": "环境温度", "base": 26, "range": 9, "noise": 0.7, "unit": "°C"},
            "SENSOR-ENV04_humidity": {"metric": "humidity", "label": "相对湿度", "base": 62, "range": 18, "noise": 2, "unit": "%"},
            "SENSOR-ENV04_pressure": {"metric": "pressure", "label": "大气压力", "base": 7.2, "range": 2.8, "noise": 0.28, "unit": "bar"},
            "SENSOR-ENV04_flow_rate": {"metric": "flow_rate", "label": "冷却液流量", "base": 130, "range": 45, "noise": 6, "unit": "L/min"},
        },
    },
    "PLC-LINE-D": {
        "device_type": "plc",
        "workshop": "workshop-4",
        "line": "line-D",
        "points": {
            "PLC-LINE-D_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 2.2},
            "PLC-LINE-D_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 0.09},
            "PLC-LINE-D_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 97, "range": 3, "noise": 0.4, "unit": "%"},
            "PLC-LINE-D_oee": {"metric": "oee", "label": "设备综合效率(OEE)", "base": 88, "range": 12, "noise": 1.5, "unit": "%"},
            "PLC-LINE-D_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 25, "range": 8, "noise": 1.5, "unit": "s"},
        },
    },
    # ===== 车间5：四川成都 =====
    "CNC-E01": {
        "device_type": "cnc",
        "workshop": "workshop-5",
        "line": "line-E",
        "points": {
            "CNC-E01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴前轴承温度", "base": 52, "range": 20, "noise": 2.8, "unit": "°C"},
            "CNC-E01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴后轴承温度", "base": 50, "range": 18, "noise": 2.6, "unit": "°C"},
            "CNC-E01_motor_winding_temp": {"metric": "temperature", "label": "电机绕组温度", "base": 55, "range": 24, "noise": 3.2, "unit": "°C"},
            "CNC-E01_vibration": {"metric": "vibration", "label": "主轴振动", "base": 2.2, "range": 3.2, "noise": 0.5, "unit": "mm/s"},
            "CNC-E01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3800, "range": 2800, "noise": 120, "unit": "rpm"},
            "CNC-E01_power": {"metric": "power", "label": "功率消耗", "base": 5800, "range": 4200, "noise": 400, "unit": "W"},
            "CNC-E01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 1700, "range": 1300, "noise": 70, "unit": "mm/min"},
            "CNC-E01_voltage": {"metric": "voltage", "label": "电源电压", "base": 380, "range": 14, "noise": 3, "unit": "V"},
            "CNC-E01_current": {"metric": "current", "label": "工作电流", "base": 17, "range": 11, "noise": 0.7, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-E02": {
        "device_type": "cnc",
        "workshop": "workshop-5",
        "line": "line-E",
        "points": {
            "CNC-E02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴前轴承温度", "base": 40, "range": 11, "noise": 1.6, "unit": "°C"},
            "CNC-E02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴后轴承温度", "base": 38, "range": 10, "noise": 1.4, "unit": "°C"},
            "CNC-E02_motor_winding_temp": {"metric": "temperature", "label": "电机绕组温度", "base": 42, "range": 14, "noise": 2.0, "unit": "°C"},
            "CNC-E02_vibration": {"metric": "vibration", "label": "主轴振动", "base": 1.0, "range": 1.5, "noise": 0.25, "unit": "mm/s"},
            "CNC-E02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 2600, "range": 1600, "noise": 50, "unit": "rpm"},
            "CNC-E02_power": {"metric": "power", "label": "功率消耗", "base": 3800, "range": 2400, "noise": 180, "unit": "W"},
            "CNC-E02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 1000, "range": 600, "noise": 25, "unit": "mm/min"},
            "CNC-E02_voltage": {"metric": "voltage", "label": "电源电压", "base": 380, "range": 7, "noise": 1.2, "unit": "V"},
            "CNC-E02_current": {"metric": "current", "label": "工作电流", "base": 10, "range": 4, "noise": 0.2, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-ENV05": {
        "device_type": "sensor",
        "workshop": "workshop-5",
        "line": "line-E",
        "points": {
            "SENSOR-ENV05_temperature": {"metric": "temperature", "label": "环境温度", "base": 24, "range": 12, "noise": 0.8, "unit": "°C"},
            "SENSOR-ENV05_humidity": {"metric": "humidity", "label": "相对湿度", "base": 65, "range": 20, "noise": 3, "unit": "%"},
            "SENSOR-ENV05_pressure": {"metric": "pressure", "label": "大气压力", "base": 6.0, "range": 2.2, "noise": 0.3, "unit": "bar"},
            "SENSOR-ENV05_flow_rate": {"metric": "flow_rate", "label": "冷却液流量", "base": 90, "range": 30, "noise": 3, "unit": "L/min"},
        },
    },
    "PLC-LINE-E": {
        "device_type": "plc",
        "workshop": "workshop-5",
        "line": "line-E",
        "points": {
            "PLC-LINE-E_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 1.3},
            "PLC-LINE-E_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "pcs", "accumulator": True, "rate": 0.15},
            "PLC-LINE-E_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 92, "range": 8, "noise": 1, "unit": "%"},
            "PLC-LINE-E_oee": {"metric": "oee", "label": "设备综合效率(OEE)", "base": 80, "range": 20, "noise": 3.5, "unit": "%"},
            "PLC-LINE-E_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 38, "range": 14, "noise": 2.5, "unit": "s"},
        },
    },
}

# 车间地理信息映射
WORKSHOP_GEO = {
    "workshop-1": {"province": "广东省", "city": "深圳", "lat": 22.5431, "lng": 114.0579, "name": "深圳数控车间"},
    "workshop-2": {"province": "江苏省", "city": "苏州", "lat": 31.2990, "lng": 120.5853, "name": "苏州精密车间"},
    "workshop-3": {"province": "山东省", "city": "青岛", "lat": 36.0671, "lng": 120.3826, "name": "青岛模具车间"},
    "workshop-4": {"province": "浙江省", "city": "杭州", "lat": 30.2741, "lng": 120.1551, "name": "杭州电子车间"},
    "workshop-5": {"province": "四川省", "city": "成都", "lat": 30.5728, "lng": 104.0668, "name": "成都重装车间"},
}

# ==================== 数据生成引擎 ====================

class IndustrialDataEngine:
    """基于正弦波 + 噪声的工业数据生成器 — 支持点位+设备聚合"""

    def __init__(self):
        self.t = 0
        self.accumulators = {}
        for dev_id, dev in DEVICES.items():
            for point_id, point_cfg in dev.get("points", {}).items():
                if point_cfg.get("accumulator"):
                    self.accumulators[point_id] = point_cfg["base"]

    def generate_point(self, point_id: str, point_cfg: dict) -> float:
        """生成单个点位指标数据"""
        self.t += 0.01

        if point_cfg.get("accumulator"):
            rate = point_cfg["rate"] * random.uniform(0.8, 1.2)
            self.accumulators[point_id] += rate
            return round(self.accumulators[point_id])

        base = point_cfg["base"]
        rng = point_cfg["range"]
        noise = point_cfg["noise"]
        metric = point_cfg["metric"]

        cycle = math.sin(self.t * 0.1 + hash(point_id) % 100) * rng * 0.3
        drift = math.sin(self.t * 0.01 + hash(point_id + metric) % 50) * rng * 0.15
        gaussian_noise = np.random.normal(0, noise)

        spike = 0
        if random.random() < 0.05:
            spike = random.uniform(-rng * 0.4, rng * 0.4)

        value = base + cycle + drift + gaussian_noise + spike

        if metric in ["rpm", "power", "count", "defect_count"]:
            value = max(0, value)
        if metric == "humidity":
            value = max(0, min(100, value))
        if metric in ["quality_rate", "oee"]:
            value = max(0, min(100, value))

        return round(value, 2)

    def compute_device_stats(self, dev_id: str) -> dict:
        """根据所有点位数据计算设备级聚合统计"""
        dev = DEVICES[dev_id]
        stats = {}
        for stat_name, stat_cfg in dev.get("stats", {}).items():
            src_metric = stat_cfg["source_metric"]
            agg = stat_cfg["agg"]
            # 收集该设备下所有同 source_metric 的点位的值
            values = []
            for point_id, point_cfg in dev.get("points", {}).items():
                if point_cfg["metric"] == src_metric:
                    values.append(self.generate_point(point_id, point_cfg))
            if not values:
                continue
            if agg == "mean":
                stats[stat_name] = round(sum(values) / len(values), 2)
            elif agg == "max":
                stats[stat_name] = round(max(values), 2)
            elif agg == "min":
                stats[stat_name] = round(min(values), 2)
        return stats


engine = IndustrialDataEngine()

# ==================== MQTT 发布器 ====================

def mqtt_publisher():
    """每 3 秒生成并发布点位数据 + 设备统计数据"""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="industrial-simulator")

    def on_connect(c, userdata, flags, reason_code, properties):
        print(f"[MQTT] 已连接到 {MQTT_HOST}:{MQTT_PORT}, reason_code={reason_code}")

    def on_disconnect(c, userdata, flags, reason_code, properties):
        print(f"[MQTT] 断开连接, reason_code={reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

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
            # 使用固定时间戳保证同一轮所有数据点时间一致
            ts = datetime.now(timezone.utc).isoformat()
            for dev_id, dev in DEVICES.items():
                device_type = dev["device_type"]
                topic_prefix = f"factory/{device_type}/{dev_id}"
                base_tags = {
                    "machine_id": dev_id,
                    "device_type": device_type,
                    "workshop": dev["workshop"],
                    "line": dev["line"],
                    "timestamp": ts,
                }

                # 1. 发布每个点位的数据
                for point_id, point_cfg in dev.get("points", {}).items():
                    val = engine.generate_point(point_id, point_cfg)
                    point_payload = {
                        **base_tags,
                        "point_id": point_id,
                        "status": random.choice(["running", "running", "running", "running", "idle", "warning"]),
                        point_cfg["metric"]: val,
                    }
                    client.publish(topic_prefix, json.dumps(point_payload), qos=1)

                # 2. 计算并发布设备统计数据
                stats = engine.compute_device_stats(dev_id)
                stats_payload = {
                    **base_tags,
                    "status": "running",
                }
                stats_payload.update(stats)
                client.publish(topic_prefix, json.dumps(stats_payload), qos=1)

            time.sleep(3)
        except Exception as e:
            print(f"[MQTT] 发布错误: {e}")
            time.sleep(5)


# ==================== HTTP REST API ====================

app = Flask(__name__)


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Telegraf HTTP 插件拉取接口 — 返回点位数据 + 设备统计"""
    results = []
    for dev_id, dev in DEVICES.items():
        base_row = {
            "machine_id": dev_id,
            "device_type": dev["device_type"],
            "workshop": dev["workshop"],
            "line": dev["line"],
            "status": "running",
        }
        # 点位数据
        for point_id, point_cfg in dev.get("points", {}).items():
            val = engine.generate_point(point_id, point_cfg)
            row = {**base_row, "point_id": point_id, point_cfg["metric"]: val}
            results.append(row)
        # 设备统计
        stats = engine.compute_device_stats(dev_id)
        stats_row = {**base_row}
        stats_row.update(stats)
        results.append(stats_row)
    return jsonify(results)


@app.route("/api/devices", methods=["GET"])
def get_devices():
    """返回设备列表（含点位信息）"""
    devices = []
    for dev_id, dev in DEVICES.items():
        points_info = []
        for pid, pcfg in dev.get("points", {}).items():
            points_info.append({
                "point_id": pid,
                "metric": pcfg["metric"],
                "label": pcfg["label"],
                "unit": pcfg.get("unit", ""),
            })
        devices.append({
            "id": dev_id,
            "type": dev["device_type"],
            "workshop": dev["workshop"],
            "line": dev["line"],
            "points": points_info,
            "stats": list(dev.get("stats", {}).keys()),
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
    total_points = sum(len(d.get("points", {}
