"""
系统基础路由：首页、系统状态
"""

import os
import requests

from flask import Blueprint, jsonify, render_template, send_from_directory, session, redirect, url_for

from auth import login_required
from config import INFLUXDB_URL
from logger import get_logger

# TLS 验证配置（与 db.py 一致）
_CA_CERT = os.getenv("INFLUXDB_CA_CERT")
_VERIFY_TLS = os.getenv("VERIFY_TLS", "true").lower() not in ("false", "0", "no")

logger = get_logger(__name__)

bp = Blueprint("system", __name__)

# React 构建产物目录
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
BUILD_INDEX = os.path.join(STATIC_DIR, "index.html")


@bp.route("/")
@login_required
def index():
    """管理后台首页（管理员重定向到用户管理页）"""
    if session.get("role") == "admin":
        return redirect(url_for("auth.admin_users_page"))
    # 生产模式 Serve React build；开发模式 Fallback 到旧版模板
    if os.path.isfile(BUILD_INDEX):
        resp = send_from_directory(STATIC_DIR, "index.html")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    return render_template("index.html")


@bp.route("/assets/<path:filename>")
def static_assets(filename):
    """React 构建产物 — JS/CSS/字体"""
    resp = send_from_directory(os.path.join(STATIC_DIR, "assets"), filename)
    # 带 hash 的静态资源可以长期缓存，但 index.html 引用的旧文件不再存在时需要重新加载
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@bp.route("/china.json")
def china_geojson():
    """中国地图 GeoJSON"""
    geojson_path = os.path.join(STATIC_DIR, "china.json")
    if os.path.isfile(geojson_path):
        return send_from_directory(STATIC_DIR, "china.json")
    return jsonify({}), 404


@bp.route("/logo.png")
def logo():
    """Logo 图片"""
    logo_path = os.path.join(STATIC_DIR, "logo.png")
    if os.path.isfile(logo_path):
        return send_from_directory(STATIC_DIR, "logo.png")
    return "", 404


@bp.route("/api/system/status")
@login_required
def system_status():
    """系统各组件状态"""
    try:
        verify = _CA_CERT if _CA_CERT else _VERIFY_TLS
        r = requests.get(f"{INFLUXDB_URL}/health", timeout=3, verify=verify)
        influx_status = "online" if r.status_code == 200 else "error"
    except Exception:
        influx_status = "offline"

    services = [
        {"name": "InfluxDB", "status": influx_status, "port": 8086},
        {"name": "Telegraf", "status": "online", "port": 0},
        {"name": "Grafana", "status": "online", "port": 3000, "url": "http://localhost:3000"},
        {"name": "Mosquitto MQTT", "status": "online", "port": 1883},
        {"name": "Simulator", "status": "online", "port": 5001},
        {"name": "Manager", "status": "online", "port": 5000},
    ]
    return jsonify(services)
