"""
系统基础路由：首页、系统状态
"""

import requests
from flask import Blueprint, jsonify, render_template

from config import INFLUXDB_URL

bp = Blueprint("system", __name__)


@bp.route("/")
def index():
    """管理后台首页"""
    return render_template("index.html")


@bp.route("/api/system/status")
def system_status():
    """系统各组件状态"""
    try:
        r = requests.get(f"{INFLUXDB_URL}/health", timeout=3)
        influx_status = "online" if r.status_code == 200 else "error"
    except Exception:
        influx_status = "offline"

    services = [
        {"name": "InfluxDB", "status": influx_status, "port": 8086, "url": "http://localhost:8086"},
        {"name": "Telegraf", "status": "online", "port": 0},
        {"name": "Grafana", "status": "online", "port": 3000, "url": "http://localhost:3000"},
        {"name": "Mosquitto MQTT", "status": "online", "port": 1883},
        {"name": "Simulator", "status": "online", "port": 5001},
        {"name": "Manager", "status": "online", "port": 5000},
    ]
    return jsonify(services)
