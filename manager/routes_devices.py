"""
设备数据路由：设备树、最新数据、历史数据、统计摘要
"""

import requests
from flask import Blueprint, jsonify, request

from config import DEVICE_TYPE_CN, SIMULATOR_URL
from db import query_influxdb

bp = Blueprint("devices", __name__)


@bp.route("/api/devices/tree")
def devices_tree():
    """获取设备树（设备 → 点位级最新值），用于嵌套表格展示"""
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        meta_devices = resp.json()
    except Exception as e:
        print(f"获取 simulator 元数据失败: {e}")
        return jsonify([])

    project_id = request.args.get("project_id", "")
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    result = []
    for dev in meta_devices:
        dev_id = dev.get("id")
        if not dev_id:
            continue
        points_meta = dev.get("points", []) or []

        point_values = {}
        metrics_set = sorted({p.get("metric") for p in points_meta if p.get("metric")})
        for metric in metrics_set:
            flux = f'''
            from(bucket: "factory")
              |> range(start: -10m)
              |> filter(fn: (r) => r._measurement == "industrial_metrics")
              |> filter(fn: (r) => r.machine_id == "{dev_id}")
              |> filter(fn: (r) => r._field == "{metric}")
              {project_filter}
              |> last()
            '''
            rows = query_influxdb(flux)
            for r in rows:
                pid = r.get("point_id", "")
                try:
                    val = float(r.get("_value", 0))
                except (ValueError, TypeError):
                    continue
                if pid:
                    point_values[pid] = val

        points = []
        for p in points_meta:
            pid = p.get("point_id", "")
            points.append({
                "point_id": pid,
                "label": p.get("label", ""),
                "metric": p.get("metric", ""),
                "unit": p.get("unit", ""),
                "value": point_values.get(pid),
            })

        result.append({
            "device_id": dev_id,
            "device_type": dev.get("type", ""),
            "device_type_cn": DEVICE_TYPE_CN.get(dev.get("type", ""), dev.get("type", "")),
            "workshop": dev.get("workshop", ""),
            "points": points,
        })

    return jsonify(result)


@bp.route("/api/devices/latest")
def devices_latest():
    """获取所有设备最新数据"""
    flux = '''
    from(bucket: "factory")
      |> range(start: -5m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "temperature")
      |> last()
      |> group(columns: ["machine_id"])
    '''
    base_rows = query_influxdb(flux)

    valid_ids = []
    for r in base_rows:
        mid = r.get("machine_id", "")
        if mid and "-" in mid and not mid.startswith("line"):
            valid_ids.append(mid)

    seen = set()
    unique_ids = []
    for mid in valid_ids:
        if mid not in seen:
            seen.add(mid)
            unique_ids.append(mid)

    devices = []
    for mid in unique_ids:
        flux2 = f'''
        from(bucket: "factory")
          |> range(start: -5m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r.machine_id == "{mid}")
          |> last()
          |> pivot(rowKey: ["machine_id"], columnKey: ["_field"], valueColumn: "_value")
        '''
        rows = query_influxdb(flux2)
        if rows:
            devices.append(rows[0])
    return jsonify(devices)


@bp.route("/api/metrics/history")
def metrics_history():
    """获取指定指标的历史数据"""
    metric = request.args.get("metric", "temperature")
    device = request.args.get("device", "")
    minutes = int(request.args.get("minutes", 30))

    device_filter = f'|> filter(fn: (r) => r.machine_id == "{device}")' if device else ""

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{metric}")
      {device_filter}
      |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
      |> limit(n: 200)
    '''
    results = query_influxdb(flux)
    return jsonify(results)


@bp.route("/api/stats/summary")
def stats_summary():
    """获取数据统计摘要"""
    flux = '''
    from(bucket: "factory")
      |> range(start: -1h)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration" or r._field == "power")
      |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
      |> group(columns: ["_field"])
      |> mean()
    '''
    results = query_influxdb(flux)
    return jsonify(results)
