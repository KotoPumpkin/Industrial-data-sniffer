"""
设备数据路由：设备树、最新数据、历史数据、统计摘要
"""

import requests
import statistics
from flask import Blueprint, jsonify, request

from auth import login_required
from config import DEVICE_TYPE_CN, DEVICES, SIMULATOR_URL
from db import query_influxdb
from logger import get_logger
from validators import sanitize_project, sanitize_metric, sanitize_device, sanitize_int, ValidationError

logger = get_logger(__name__)

bp = Blueprint("devices", __name__)


@bp.route("/api/devices/tree")
@login_required
def devices_tree():
    """获取设备树（设备 → 点位级最新值），用于嵌套表格展示"""
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        meta_devices = resp.json()
    except Exception as e:
        logger.warning(f"获取 simulator 元数据失败: {e}")
        return jsonify([])

    project_id = sanitize_project(request.args.get("project_id"))
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    result = []
    for dev in meta_devices:
        dev_id = dev.get("id")
        if not dev_id:
            continue
        # Python 侧按 project_id 过滤设备列表
        if project_id:
            dev_info = DEVICES.get(dev_id, {})
            if dev_info.get("project_id") != project_id:
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
@login_required
def devices_latest():
    """获取所有设备最新数据"""
    project_id = sanitize_project(request.args.get("project_id"))
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    flux = f'''
    from(bucket: "factory")
      |> range(start: -5m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "temperature")
      {project_filter}
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
          {project_filter}
          |> last()
          |> pivot(rowKey: ["machine_id"], columnKey: ["_field"], valueColumn: "_value")
        '''
        rows = query_influxdb(flux2)
        if rows:
            devices.append(rows[0])
    return jsonify(devices)


@bp.route("/api/metrics/history")
@login_required
def metrics_history():
    """获取指定指标的历史数据"""
    metric = sanitize_metric(request.args.get("metric"))
    device = sanitize_device(request.args.get("device"), required=True)
    minutes = sanitize_int(request.args.get("minutes"), default=30)

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


@bp.route("/api/metrics/history/batch")
@login_required
def metrics_history_batch():
    """批量获取多个设备同一指标的历史数据"""
    metric = sanitize_metric(request.args.get("metric"))
    devices_str = request.args.get("devices", "")
    devices = [d.strip() for d in devices_str.split(",") if d.strip()]
    minutes = sanitize_int(request.args.get("minutes"), default=30)

    series = {}
    for device in devices:
        safe_device = sanitize_device(device, required=True)
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric}")
          |> filter(fn: (r) => r.machine_id == "{safe_device}")
          |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
          |> limit(n: 200)
        '''
        rows = query_influxdb(flux)
        if rows:
            series[safe_device] = rows

    return jsonify({"metric": metric, "minutes": minutes, "series": series})


@bp.route("/api/metrics/point_detail")
@login_required
def metrics_point_detail():
    """点位综合数据 — 合并 history + anomalies + trend + report"""
    metric = sanitize_metric(request.args.get("metric"))
    device = sanitize_device(request.args.get("device"), required=True)
    minutes = sanitize_int(request.args.get("minutes"), default=30)

    # History
    flux_hist = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{metric}")
      |> filter(fn: (r) => r.machine_id == "{device}")
      |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
      |> limit(n: 200)
    '''
    history = query_influxdb(flux_hist)

    # Anomalies (Z-score)
    flux_anom = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{metric}")
      |> filter(fn: (r) => r.machine_id == "{device}")
      |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
    '''
    anom_rows = query_influxdb(flux_anom)
    anomalies = []
    if len(anom_rows) >= 5:
        vals = []
        for r in anom_rows:
            try:
                v = float(r.get("_value", 0))
                t = r.get("_time", "")
                vals.append({"value": v, "time": t})
            except (ValueError, TypeError):
                continue
        if vals:
            raw = [v["value"] for v in vals]
            mean_v = statistics.mean(raw)
            stdev_v = statistics.stdev(raw) if len(raw) > 1 else 0
            if stdev_v > 0:
                for v in vals:
                    z = abs(v["value"] - mean_v) / stdev_v
                    if z > 2.0:
                        anomalies.append({
                            "time": v["time"], "value": v["value"],
                            "z_score": round(z, 3),
                            "severity": "high" if z > 3.0 else "medium" if z > 2.5 else "low",
                        })

    # Trend direction
    trend_info = {"trend": "stable", "slope": 0, "change_from_start": 0}
    if len(history) >= 3:
        try:
            vals_hist = []
            for r in history:
                try:
                    vals_hist.append(float(r.get("_value", 0)))
                except (ValueError, TypeError):
                    continue
            if len(vals_hist) >= 3:
                n = len(vals_hist)
                x_mean = (n - 1) / 2
                y_mean = statistics.mean(vals_hist)
                numerator = sum((i - x_mean) * (vals_hist[i] - y_mean) for i in range(n))
                denominator = sum((i - x_mean) ** 2 for i in range(n))
                slope = numerator / denominator if denominator != 0 else 0
                stdev_hist = statistics.stdev(vals_hist) if len(vals_hist) > 1 else 1
                if abs(slope) < 0.01 * stdev_hist:
                    trend_dir = "stable"
                elif slope > 0:
                    trend_dir = "rising"
                else:
                    trend_dir = "falling"
                trend_info = {
                    "trend": trend_dir,
                    "slope": round(slope, 4),
                    "change_from_start": round(vals_hist[-1] - vals_hist[0], 3),
                }
        except Exception:
            pass

    # Device report (stats for the metric)
    report = None
    if history:
        try:
            vals_rpt = []
            for r in history:
                try:
                    vals_rpt.append(float(r.get("_value", 0)))
                except (ValueError, TypeError):
                    continue
            if vals_rpt:
                mean_rpt = statistics.mean(vals_rpt)
                report = {
                    "metrics": {
                        metric: {
                            "mean": round(mean_rpt, 3),
                            "min": round(min(vals_rpt), 3),
                            "max": round(max(vals_rpt), 3),
                            "std": round(statistics.stdev(vals_rpt), 3) if len(vals_rpt) > 1 else 0,
                            "latest": round(vals_rpt[-1], 3),
                            "cv": round(abs(statistics.stdev(vals_rpt) / mean_rpt) * 100, 2) if len(vals_rpt) > 1 and mean_rpt != 0 else 0,
                        }
                    }
                }
        except Exception:
            pass

    return jsonify({
        "metric": metric, "device": device, "minutes": minutes,
        "history": history, "anomalies": anomalies,
        "trend_info": trend_info, "report": report,
    })


@bp.route("/api/stats/summary")
@login_required
def stats_summary():
    """获取数据统计摘要"""
    project_id = sanitize_project(request.args.get("project_id"))
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    flux = f'''
    from(bucket: "factory")
      |> range(start: -1h)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration" or r._field == "power")
      {project_filter}
      |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
      |> group(columns: ["_field"])
      |> mean()
    '''
    results = query_influxdb(flux)
    return jsonify(results)
