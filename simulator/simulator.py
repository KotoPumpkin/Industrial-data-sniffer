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
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
HTTP_PORT = int(os.getenv("HTTP_PORT", 5001))

# ==================== 项目定义 ====================
PROJECTS = {
    "project-huadong": {
        "name": "华东制造基地",
        "color": "#3b82f6",
        "provinces": ["广东省", "江苏省", "浙江省"],
    },
    "project-beifang": {
        "name": "北方工业中心",
        "color": "#fb923c",
        "provinces": ["山东省", "天津市", "辽宁省"],
    },
    "project-xinan": {
        "name": "西南智造园区",
        "color": "#34d399",
        "provinces": ["四川省", "重庆市", "云南省"],
    },
}

# ==================== 车间地理信息 ====================
WORKSHOP_GEO = {
    "workshop-sz":  {"project_id": "project-huadong", "province": "广东省", "city": "深圳", "name": "深圳数控车间", "lat": 22.5431, "lng": 114.0579},
    "workshop-szh": {"project_id": "project-huadong", "province": "江苏省", "city": "苏州", "name": "苏州精密车间", "lat": 31.2990, "lng": 120.5853},
    "workshop-hz":  {"project_id": "project-huadong", "province": "浙江省", "city": "杭州", "name": "杭州电子车间", "lat": 30.2741, "lng": 120.1551},
    "workshop-qd":  {"project_id": "project-beifang", "province": "山东省", "city": "青岛", "name": "青岛模具车间", "lat": 36.0671, "lng": 120.3826},
    "workshop-tj":  {"project_id": "project-beifang", "province": "天津市", "city": "天津", "name": "天津装配车间", "lat": 39.0842, "lng": 117.2009},
    "workshop-dl":  {"project_id": "project-beifang", "province": "辽宁省", "city": "大连", "name": "大连重工车间", "lat": 38.9140, "lng": 121.6147},
    "workshop-cd":  {"project_id": "project-xinan",   "province": "四川省", "city": "成都", "name": "成都重装车间", "lat": 30.5728, "lng": 104.0668},
    "workshop-cq":  {"project_id": "project-xinan",   "province": "重庆市", "city": "重庆", "name": "重庆模具车间", "lat": 29.4316, "lng": 106.9123},
    "workshop-km":  {"project_id": "project-xinan",   "province": "云南省", "city": "昆明", "name": "昆明精工车间", "lat": 25.0389, "lng": 102.7183},
}

# ==================== 设备定义 ====================
# 结构: 设备 → 点位(points) → 指标数据 + 设备级聚合统计(stats)
DEVICES = {
    # ===== workshop-sz: 深圳数控车间 (project-huadong) =====
    "CNC-SZ01": {
        "device_type": "cnc",
        "project_id": "project-huadong",
        "workshop": "workshop-sz",
        "line": "line-SZ",
        "points": {
            "CNC-SZ01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-SZ01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-SZ01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-SZ01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-SZ01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-SZ01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-SZ01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-SZ01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-SZ01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-SZ02": {
        "device_type": "cnc",
        "project_id": "project-huadong",
        "workshop": "workshop-sz",
        "line": "line-SZ",
        "points": {
            "CNC-SZ02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-SZ02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-SZ02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-SZ02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-SZ02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-SZ02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-SZ02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-SZ02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-SZ02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-SZ01": {
        "device_type": "sensor",
        "project_id": "project-huadong",
        "workshop": "workshop-sz",
        "line": "line-SZ",
        "points": {
            "SENSOR-SZ01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-SZ01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-SZ01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-SZ01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-SZ01": {
        "device_type": "plc",
        "project_id": "project-huadong",
        "workshop": "workshop-sz",
        "line": "line-SZ",
        "points": {
            "PLC-SZ01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-SZ01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-SZ01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-SZ01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-SZ01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
    # ===== workshop-szh: 苏州精密车间 (project-huadong) =====
    "CNC-SZH01": {
        "device_type": "cnc",
        "project_id": "project-huadong",
        "workshop": "workshop-szh",
        "line": "line-SZH",
        "points": {
            "CNC-SZH01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-SZH01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-SZH01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-SZH01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-SZH01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-SZH01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-SZH01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-SZH01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-SZH01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-SZH02": {
        "device_type": "cnc",
        "project_id": "project-huadong",
        "workshop": "workshop-szh",
        "line": "line-SZH",
        "points": {
            "CNC-SZH02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-SZH02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-SZH02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-SZH02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-SZH02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-SZH02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-SZH02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-SZH02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-SZH02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-SZH01": {
        "device_type": "sensor",
        "project_id": "project-huadong",
        "workshop": "workshop-szh",
        "line": "line-SZH",
        "points": {
            "SENSOR-SZH01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-SZH01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-SZH01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-SZH01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-SZH01": {
        "device_type": "plc",
        "project_id": "project-huadong",
        "workshop": "workshop-szh",
        "line": "line-SZH",
        "points": {
            "PLC-SZH01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-SZH01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-SZH01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-SZH01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-SZH01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
    # ===== workshop-hz: 杭州电子车间 (project-huadong) =====
    "CNC-HZ01": {
        "device_type": "cnc",
        "project_id": "project-huadong",
        "workshop": "workshop-hz",
        "line": "line-HZ",
        "points": {
            "CNC-HZ01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-HZ01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-HZ01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-HZ01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-HZ01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-HZ01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-HZ01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-HZ01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-HZ01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-HZ02": {
        "device_type": "cnc",
        "project_id": "project-huadong",
        "workshop": "workshop-hz",
        "line": "line-HZ",
        "points": {
            "CNC-HZ02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-HZ02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-HZ02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-HZ02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-HZ02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-HZ02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-HZ02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-HZ02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-HZ02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-HZ01": {
        "device_type": "sensor",
        "project_id": "project-huadong",
        "workshop": "workshop-hz",
        "line": "line-HZ",
        "points": {
            "SENSOR-HZ01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-HZ01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-HZ01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-HZ01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-HZ01": {
        "device_type": "plc",
        "project_id": "project-huadong",
        "workshop": "workshop-hz",
        "line": "line-HZ",
        "points": {
            "PLC-HZ01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-HZ01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-HZ01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-HZ01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-HZ01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
    # ===== workshop-qd: 青岛模具车间 (project-beifang) =====
    "CNC-QD01": {
        "device_type": "cnc",
        "project_id": "project-beifang",
        "workshop": "workshop-qd",
        "line": "line-QD",
        "points": {
            "CNC-QD01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-QD01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-QD01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-QD01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-QD01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-QD01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-QD01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-QD01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-QD01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-QD02": {
        "device_type": "cnc",
        "project_id": "project-beifang",
        "workshop": "workshop-qd",
        "line": "line-QD",
        "points": {
            "CNC-QD02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-QD02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-QD02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-QD02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-QD02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-QD02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-QD02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-QD02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-QD02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-QD01": {
        "device_type": "sensor",
        "project_id": "project-beifang",
        "workshop": "workshop-qd",
        "line": "line-QD",
        "points": {
            "SENSOR-QD01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-QD01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-QD01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-QD01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-QD01": {
        "device_type": "plc",
        "project_id": "project-beifang",
        "workshop": "workshop-qd",
        "line": "line-QD",
        "points": {
            "PLC-QD01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-QD01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-QD01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-QD01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-QD01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
    # ===== workshop-tj: 天津装配车间 (project-beifang) =====
    "CNC-TJ01": {
        "device_type": "cnc",
        "project_id": "project-beifang",
        "workshop": "workshop-tj",
        "line": "line-TJ",
        "points": {
            "CNC-TJ01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-TJ01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-TJ01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-TJ01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-TJ01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-TJ01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-TJ01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-TJ01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-TJ01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-TJ02": {
        "device_type": "cnc",
        "project_id": "project-beifang",
        "workshop": "workshop-tj",
        "line": "line-TJ",
        "points": {
            "CNC-TJ02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-TJ02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-TJ02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-TJ02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-TJ02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-TJ02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-TJ02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-TJ02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-TJ02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-TJ01": {
        "device_type": "sensor",
        "project_id": "project-beifang",
        "workshop": "workshop-tj",
        "line": "line-TJ",
        "points": {
            "SENSOR-TJ01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-TJ01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-TJ01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-TJ01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-TJ01": {
        "device_type": "plc",
        "project_id": "project-beifang",
        "workshop": "workshop-tj",
        "line": "line-TJ",
        "points": {
            "PLC-TJ01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-TJ01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-TJ01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-TJ01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-TJ01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
    # ===== workshop-dl: 大连重工车间 (project-beifang) =====
    "CNC-DL01": {
        "device_type": "cnc",
        "project_id": "project-beifang",
        "workshop": "workshop-dl",
        "line": "line-DL",
        "points": {
            "CNC-DL01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-DL01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-DL01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-DL01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-DL01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-DL01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-DL01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-DL01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-DL01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-DL02": {
        "device_type": "cnc",
        "project_id": "project-beifang",
        "workshop": "workshop-dl",
        "line": "line-DL",
        "points": {
            "CNC-DL02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-DL02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-DL02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-DL02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-DL02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-DL02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-DL02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-DL02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-DL02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-DL01": {
        "device_type": "sensor",
        "project_id": "project-beifang",
        "workshop": "workshop-dl",
        "line": "line-DL",
        "points": {
            "SENSOR-DL01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-DL01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-DL01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-DL01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-DL01": {
        "device_type": "plc",
        "project_id": "project-beifang",
        "workshop": "workshop-dl",
        "line": "line-DL",
        "points": {
            "PLC-DL01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-DL01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-DL01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-DL01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-DL01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
    # ===== workshop-cd: 成都重装车间 (project-xinan) =====
    "CNC-CD01": {
        "device_type": "cnc",
        "project_id": "project-xinan",
        "workshop": "workshop-cd",
        "line": "line-CD",
        "points": {
            "CNC-CD01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-CD01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-CD01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-CD01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-CD01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-CD01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-CD01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-CD01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-CD01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-CD02": {
        "device_type": "cnc",
        "project_id": "project-xinan",
        "workshop": "workshop-cd",
        "line": "line-CD",
        "points": {
            "CNC-CD02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-CD02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-CD02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-CD02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-CD02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-CD02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-CD02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-CD02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-CD02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-CD01": {
        "device_type": "sensor",
        "project_id": "project-xinan",
        "workshop": "workshop-cd",
        "line": "line-CD",
        "points": {
            "SENSOR-CD01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-CD01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-CD01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-CD01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-CD01": {
        "device_type": "plc",
        "project_id": "project-xinan",
        "workshop": "workshop-cd",
        "line": "line-CD",
        "points": {
            "PLC-CD01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-CD01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-CD01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-CD01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-CD01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
    # ===== workshop-cq: 重庆模具车间 (project-xinan) =====
    "CNC-CQ01": {
        "device_type": "cnc",
        "project_id": "project-xinan",
        "workshop": "workshop-cq",
        "line": "line-CQ",
        "points": {
            "CNC-CQ01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-CQ01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-CQ01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-CQ01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-CQ01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-CQ01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-CQ01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-CQ01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-CQ01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-CQ02": {
        "device_type": "cnc",
        "project_id": "project-xinan",
        "workshop": "workshop-cq",
        "line": "line-CQ",
        "points": {
            "CNC-CQ02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-CQ02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-CQ02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-CQ02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-CQ02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-CQ02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-CQ02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-CQ02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-CQ02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-CQ01": {
        "device_type": "sensor",
        "project_id": "project-xinan",
        "workshop": "workshop-cq",
        "line": "line-CQ",
        "points": {
            "SENSOR-CQ01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-CQ01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-CQ01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-CQ01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-CQ01": {
        "device_type": "plc",
        "project_id": "project-xinan",
        "workshop": "workshop-cq",
        "line": "line-CQ",
        "points": {
            "PLC-CQ01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-CQ01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-CQ01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-CQ01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-CQ01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
    # ===== workshop-km: 昆明精工车间 (project-xinan) =====
    "CNC-KM01": {
        "device_type": "cnc",
        "project_id": "project-xinan",
        "workshop": "workshop-km",
        "line": "line-KM",
        "points": {
            "CNC-KM01_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-KM01_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-KM01_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-KM01_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-KM01_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-KM01_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-KM01_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-KM01_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-KM01_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "CNC-KM02": {
        "device_type": "cnc",
        "project_id": "project-xinan",
        "workshop": "workshop-km",
        "line": "line-KM",
        "points": {
            "CNC-KM02_sp_bearing_temp_1": {"metric": "temperature", "label": "主轴温度1", "base": 45, "range": 10, "noise": 1.5, "unit": "°C"},
            "CNC-KM02_sp_bearing_temp_2": {"metric": "temperature", "label": "主轴温度2", "base": 42, "range": 8, "noise": 1.2, "unit": "°C"},
            "CNC-KM02_sp_bearing_temp_3": {"metric": "temperature", "label": "主轴温度3", "base": 40, "range": 6, "noise": 1.0, "unit": "°C"},
            "CNC-KM02_vibration": {"metric": "vibration", "label": "振动幅度", "base": 1.5, "range": 2.0, "noise": 0.3, "unit": "mm/s"},
            "CNC-KM02_rpm": {"metric": "rpm", "label": "主轴转速", "base": 3500, "range": 1500, "noise": 100, "unit": "RPM"},
            "CNC-KM02_power": {"metric": "power", "label": "功率消耗", "base": 4500, "range": 2000, "noise": 300, "unit": "W"},
            "CNC-KM02_feed_rate": {"metric": "feed_rate", "label": "进给速率", "base": 2500, "range": 800, "noise": 50, "unit": "mm/min"},
            "CNC-KM02_voltage": {"metric": "voltage", "label": "电压", "base": 380, "range": 10, "noise": 2, "unit": "V"},
            "CNC-KM02_current": {"metric": "current", "label": "电流", "base": 12, "range": 5, "noise": 0.5, "unit": "A"},
        },
        "stats": {
            "avg_temperature": {"source_metric": "temperature", "agg": "mean"},
            "max_temperature": {"source_metric": "temperature", "agg": "max"},
            "max_vibration": {"source_metric": "vibration", "agg": "max"},
        },
    },
    "SENSOR-KM01": {
        "device_type": "sensor",
        "project_id": "project-xinan",
        "workshop": "workshop-km",
        "line": "line-KM",
        "points": {
            "SENSOR-KM01_env_temperature": {"metric": "temperature", "label": "环境温度", "base": 25, "range": 5, "noise": 0.5, "unit": "°C"},
            "SENSOR-KM01_env_humidity": {"metric": "humidity", "label": "相对湿度", "base": 60, "range": 15, "noise": 3, "unit": "%"},
            "SENSOR-KM01_env_pressure": {"metric": "pressure", "label": "气压", "base": 1013, "range": 5, "noise": 1, "unit": "hPa"},
            "SENSOR-KM01_env_flow_rate": {"metric": "flow_rate", "label": "流量", "base": 120, "range": 30, "noise": 5, "unit": "L/min"},
        },
    },
    "PLC-KM01": {
        "device_type": "plc",
        "project_id": "project-xinan",
        "workshop": "workshop-km",
        "line": "line-KM",
        "points": {
            "PLC-KM01_total_count": {"metric": "count", "label": "产量计数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 2},
            "PLC-KM01_defect_count": {"metric": "defect_count", "label": "不良品数", "base": 0, "range": 0, "noise": 0, "unit": "件", "accumulator": True, "rate": 0.1},
            "PLC-KM01_quality_rate": {"metric": "quality_rate", "label": "良品率", "base": 98.5, "range": 2, "noise": 0.3, "unit": "%"},
            "PLC-KM01_oee": {"metric": "oee", "label": "设备综合效率", "base": 85, "range": 10, "noise": 2, "unit": "%"},
            "PLC-KM01_cycle_time": {"metric": "cycle_time", "label": "节拍时间", "base": 45, "range": 5, "noise": 1, "unit": "s"},
        },
    },
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

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

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
                    "project_id": dev.get("project_id", ""),
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

            time.sleep(1)
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
            "project_id": dev.get("project_id", ""),
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
            "project_id": dev.get("project_id", ""),
            "points": points_info,
            "stats": list(dev.get("stats", {}).keys()),
        })
    return jsonify(devices)


@app.route("/api/projects", methods=["GET"])
def get_projects():
    """返回项目列表"""
    return jsonify([
        {"id": pid, "name": pinfo["name"], "color": pinfo["color"], "provinces": pinfo["provinces"]}
        for pid, pinfo in PROJECTS.items()
    ])


@app.route("/api/workshops", methods=["GET"])
def get_workshops():
    """返回车间地理信息列表"""
    return jsonify([
        {"id": wid, "project_id": winfo["project_id"], "province": winfo["province"],
         "city": winfo["city"], "name": winfo["name"], "lat": winfo["lat"], "lng": winfo["lng"]}
        for wid, winfo in WORKSHOP_GEO.items()
    ])


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
    total_points = sum(len(d.get("points", {})) for d in DEVICES.values())
    print(f"  点位总数: {total_points}")
    print("=" * 60)

    # 启动 MQTT 发布线程
    mqtt_thread = threading.Thread(target=mqtt_publisher, daemon=True)
    mqtt_thread.start()

    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False)
