"""
全局配置与静态数据定义
"""

import os

# ── InfluxDB ──
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "https://influxdb:8086")
INFLUXDB_TOKEN = os.environ["INFLUXDB_TOKEN"]  # 必须从环境变量注入
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "industrial")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "factory")

# ── Simulator ──
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://simulator:5001")

# ── 设备类型中文映射 ──
DEVICE_TYPE_CN = {"cnc": "CNC机床", "sensor": "环境传感器", "plc": "产线PLC"}

# ── 项目 ──
PROJECTS = {
    "project-huadong": {
        "name": "华东制造基地",
        "color": "#0ea5e9",
        "provinces": ["广东省", "江苏省", "浙江省"],
    },
    "project-beifang": {
        "name": "北方工业中心",
        "color": "#f97316",
        "provinces": ["山东省", "天津市", "辽宁省"],
    },
    "project-xinan": {
        "name": "西南智造园区",
        "color": "#22c55e",
        "provinces": ["四川省", "重庆市", "云南省"],
    },
}

# ── 车间地理信息 ──
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

# ── 采集点位定义 ──
COLLECTION_POINTS = {
    "cnc": [
        {"name": "temperature", "label": "主轴温度", "unit": "°C"},
        {"name": "vibration", "label": "振动幅度", "unit": "mm/s"},
        {"name": "rpm", "label": "主轴转速", "unit": "rpm"},
        {"name": "power", "label": "功率消耗", "unit": "W"},
        {"name": "feed_rate", "label": "进给速率", "unit": "mm/min"},
        {"name": "voltage", "label": "电压", "unit": "V"},
        {"name": "current", "label": "电流", "unit": "A"},
    ],
    "sensor": [
        {"name": "temperature", "label": "环境温度", "unit": "°C"},
        {"name": "humidity", "label": "相对湿度", "unit": "%"},
        {"name": "pressure", "label": "气压", "unit": "bar"},
        {"name": "flow_rate", "label": "流量", "unit": "L/min"},
    ],
    "plc": [
        {"name": "count", "label": "产量计数", "unit": "pcs"},
        {"name": "defect_count", "label": "不良品数", "unit": "pcs"},
        {"name": "quality_rate", "label": "良品率", "unit": "%"},
        {"name": "oee", "label": "设备综合效率", "unit": "%"},
        {"name": "cycle_time", "label": "节拍时间", "unit": "s"},
    ],
}

# ── 设备列表（紧凑定义） ──
DEVICES = {}
for _dev_id, _dev_type, _proj_id, _ws, _line_name in [
    # workshop-sz
    ("CNC-SZ01", "cnc", "project-huadong", "workshop-sz", "line-SZ"),
    ("CNC-SZ02", "cnc", "project-huadong", "workshop-sz", "line-SZ"),
    ("SENSOR-SZ01", "sensor", "project-huadong", "workshop-sz", "line-SZ"),
    ("PLC-SZ01", "plc", "project-huadong", "workshop-sz", "line-SZ"),
    # workshop-szh
    ("CNC-SZH01", "cnc", "project-huadong", "workshop-szh", "line-SZH"),
    ("CNC-SZH02", "cnc", "project-huadong", "workshop-szh", "line-SZH"),
    ("SENSOR-SZH01", "sensor", "project-huadong", "workshop-szh", "line-SZH"),
    ("PLC-SZH01", "plc", "project-huadong", "workshop-szh", "line-SZH"),
    # workshop-hz
    ("CNC-HZ01", "cnc", "project-huadong", "workshop-hz", "line-HZ"),
    ("CNC-HZ02", "cnc", "project-huadong", "workshop-hz", "line-HZ"),
    ("SENSOR-HZ01", "sensor", "project-huadong", "workshop-hz", "line-HZ"),
    ("PLC-HZ01", "plc", "project-huadong", "workshop-hz", "line-HZ"),
    # workshop-qd
    ("CNC-QD01", "cnc", "project-beifang", "workshop-qd", "line-QD"),
    ("CNC-QD02", "cnc", "project-beifang", "workshop-qd", "line-QD"),
    ("SENSOR-QD01", "sensor", "project-beifang", "workshop-qd", "line-QD"),
    ("PLC-QD01", "plc", "project-beifang", "workshop-qd", "line-QD"),
    # workshop-tj
    ("CNC-TJ01", "cnc", "project-beifang", "workshop-tj", "line-TJ"),
    ("CNC-TJ02", "cnc", "project-beifang", "workshop-tj", "line-TJ"),
    ("SENSOR-TJ01", "sensor", "project-beifang", "workshop-tj", "line-TJ"),
    ("PLC-TJ01", "plc", "project-beifang", "workshop-tj", "line-TJ"),
    # workshop-dl
    ("CNC-DL01", "cnc", "project-beifang", "workshop-dl", "line-DL"),
    ("CNC-DL02", "cnc", "project-beifang", "workshop-dl", "line-DL"),
    ("SENSOR-DL01", "sensor", "project-beifang", "workshop-dl", "line-DL"),
    ("PLC-DL01", "plc", "project-beifang", "workshop-dl", "line-DL"),
    # workshop-cd
    ("CNC-CD01", "cnc", "project-xinan", "workshop-cd", "line-CD"),
    ("CNC-CD02", "cnc", "project-xinan", "workshop-cd", "line-CD"),
    ("SENSOR-CD01", "sensor", "project-xinan", "workshop-cd", "line-CD"),
    ("PLC-CD01", "plc", "project-xinan", "workshop-cd", "line-CD"),
    # workshop-cq
    ("CNC-CQ01", "cnc", "project-xinan", "workshop-cq", "line-CQ"),
    ("CNC-CQ02", "cnc", "project-xinan", "workshop-cq", "line-CQ"),
    ("SENSOR-CQ01", "sensor", "project-xinan", "workshop-cq", "line-CQ"),
    ("PLC-CQ01", "plc", "project-xinan", "workshop-cq", "line-CQ"),
    # workshop-km
    ("CNC-KM01", "cnc", "project-xinan", "workshop-km", "line-KM"),
    ("CNC-KM02", "cnc", "project-xinan", "workshop-km", "line-KM"),
    ("SENSOR-KM01", "sensor", "project-xinan", "workshop-km", "line-KM"),
    ("PLC-KM01", "plc", "project-xinan", "workshop-km", "line-KM"),
]:
    DEVICES[_dev_id] = {"device_type": _dev_type, "project_id": _proj_id, "workshop": _ws, "line": _line_name}

# ── 告警阈值 ──
ALERT_THRESHOLDS = {
    "temperature": {"warning": 65, "critical": 80, "unit": "°C", "label": "温度"},
    "vibration": {"warning": 3.0, "critical": 4.5, "unit": "mm/s", "label": "振动"},
    "power": {"warning": 7000, "critical": 8500, "unit": "W", "label": "功率"},
    "humidity": {"warning": 75, "critical": 85, "unit": "%", "label": "湿度"},
}

# ── 标准化规则 ──
STANDARD_RULES = [
    {"name": "温度范围校验", "field": "temperature", "min": -20, "max": 120, "unit": "°C"},
    {"name": "振动阈值校验", "field": "vibration", "min": 0, "max": 10, "unit": "mm/s"},
    {"name": "转速合理性", "field": "rpm", "min": 0, "max": 12000, "unit": "rpm"},
    {"name": "功率范围校验", "field": "power", "min": 0, "max": 15000, "unit": "W"},
    {"name": "湿度范围校验", "field": "humidity", "min": 0, "max": 100, "unit": "%"},
    {"name": "良品率范围", "field": "quality_rate", "min": 0, "max": 100, "unit": "%"},
    {"name": "OEE范围", "field": "oee", "min": 0, "max": 100, "unit": "%"},
]
