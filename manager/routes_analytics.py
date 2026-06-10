"""
数据分析路由：异常检测、趋势分析、关联分析、实时告警、异常确认
"""

import json
import os
import statistics
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from config import ALERT_THRESHOLDS
from db import query_influxdb
from logger import get_logger
from validators import sanitize_project, sanitize_metric, sanitize_device, sanitize_int, sanitize_float, sanitize_choice, ValidationError
from auth import login_required
from anomaly_acks import is_anomaly_acknowledged, add_ack, get_cutoff_time

logger = get_logger(__name__)

bp = Blueprint("analytics", __name__)


@bp.route("/api/analytics/anomaly")
@login_required
def analytics_anomaly():
    """基于 Z-Score 的异常检测"""
    metric = sanitize_metric(request.args.get("metric", "temperature"))
    device = sanitize_device(request.args.get("device"))
    minutes = sanitize_int(request.args.get("minutes", "60"))
    threshold = sanitize_float(request.args.get("threshold", "2.0"))
    project_id = sanitize_project(request.args.get("project_id"))

    device_filter = f'|> filter(fn: (r) => r.machine_id == "{device}")' if device else ""
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{metric}")
      {device_filter}
      {project_filter}
      |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
    '''
    results = query_influxdb(flux)

    if len(results) < 5:
        return jsonify({"metric": metric, "anomalies": [], "total_points": len(results),
                        "anomaly_count": 0, "message": "数据点不足，至少需要5个数据点"})

    values = []
    for r in results:
        try:
            val = float(r.get("_value", 0))
            ts = r.get("_time", "")
            machine = r.get("machine_id", device)
            values.append({"time": ts, "value": val, "machine_id": machine})
        except (ValueError, TypeError):
            continue

    if not values:
        return jsonify({"metric": metric, "anomalies": [], "total_points": 0, "anomaly_count": 0})

    raw_vals = [v["value"] for v in values]
    mean_val = statistics.mean(raw_vals)
    stdev_val = statistics.stdev(raw_vals) if len(raw_vals) > 1 else 0

    anomalies = []
    if stdev_val > 0:
        for v in values:
            z_score = abs(v["value"] - mean_val) / stdev_val
            if z_score > threshold:
                anomalies.append({
                    "time": v["time"],
                    "value": v["value"],
                    "machine_id": v["machine_id"],
                    "z_score": round(z_score, 3),
                    "deviation": round(v["value"] - mean_val, 3),
                    "severity": "high" if z_score > 3.0 else "medium" if z_score > 2.5 else "low",
                })

    filtered_anomalies = [a for a in anomalies if not is_anomaly_acknowledged(metric, a.get("machine_id", ""), a.get("time", ""))]

    return jsonify({
        "metric": metric,
        "total_points": len(values),
        "anomaly_count": len(filtered_anomalies),
        "anomaly_rate": round(len(filtered_anomalies) / len(values) * 100, 2) if values else 0,
        "mean": round(mean_val, 3),
        "stdev": round(stdev_val, 3),
        "threshold": threshold,
        "anomalies": filtered_anomalies[:50],
    })


@bp.route("/api/analytics/anomaly-count")
@login_required
def analytics_anomaly_count():
    """所有指标异常检测数量总和（24小时窗口），排除已确认的异常"""
    minutes = 1440
    threshold = sanitize_float(request.args.get("threshold", "2.0"))
    project_id = sanitize_project(request.args.get("project_id"))
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""
    metrics = ["temperature", "vibration", "rpm", "power", "humidity", "pressure"]
    total_count = 0
    detail = {}

    for metric_name in metrics:
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric_name}")
          {project_filter}
          |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
        '''
        results = query_influxdb(flux)

        if len(results) < 5:
            detail[metric_name] = 0
            continue

        values = []
        for r in results:
            try:
                val = float(r.get("_value", 0))
                ts = r.get("_time", "")
                machine = r.get("machine_id", "")
                values.append({"value": val, "time": ts, "machine_id": machine})
            except (ValueError, TypeError):
                continue

        if not values:
            detail[metric_name] = 0
            continue

        raw_vals = [v["value"] for v in values]
        mean_val = statistics.mean(raw_vals)
        stdev_val = statistics.stdev(raw_vals) if len(raw_vals) > 1 else 0

        count = 0
        if stdev_val > 0:
            for v in values:
                z_score = abs(v["value"] - mean_val) / stdev_val
                if z_score > threshold and not is_anomaly_acknowledged(metric_name, v["machine_id"], v["time"]):
                    count += 1

        detail[metric_name] = count
        total_count += count

    return jsonify({
        "total_anomaly_count": total_count,
        "minutes": minutes,
        "threshold": threshold,
        "detail": detail,
    })


@bp.route("/api/analytics/anomaly/acknowledge", methods=["POST"])
@login_required
def acknowledge_anomalies():
    """确认（清除）异常记录 — 严格按 project_id / workshop 限定范围"""
    data = request.get_json() or {}
    project_id = data.get("project_id") or "*"
    workshop = data.get("workshop") or "*"
    clear_all = data.get("clear_all", False)

    if clear_all:
        add_ack({
            "metric": "*", "device": "*",
            "project_id": project_id, "workshop": workshop,
            "cutoff_time": datetime.now(timezone.utc).isoformat(),
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        })
        return jsonify({"status": "ok", "cleared": True})

    ack_entry = {
        "metric": data.get("metric", "*"),
        "device": data.get("device", "*"),
        "project_id": project_id,
        "workshop": workshop,
        "cutoff_time": "",
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
    }
    minutes = data.get("minutes", 0)
    if minutes > 0:
        ack_entry["cutoff_time"] = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    add_ack(ack_entry)
    return jsonify({"status": "ok", "cleared": True})


@bp.route("/api/analytics/trend")
@login_required
def analytics_trend():
    """趋势分析 — 移动平均、变化率、趋势方向"""
    metric = sanitize_metric(request.args.get("metric", "temperature"))
    device = sanitize_device(request.args.get("device", "CNC-A01"), required=True)
    minutes = sanitize_int(request.args.get("minutes", "60"))
    window = int(request.args.get("window", 5))
    project_id = sanitize_project(request.args.get("project_id"))
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{metric}")
      |> filter(fn: (r) => r.machine_id == "{device}")
      {project_filter}
      |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
    '''
    results = query_influxdb(flux)

    points = []
    for r in results:
        try:
            points.append({"time": r.get("_time", ""), "value": float(r.get("_value", 0))})
        except (ValueError, TypeError):
            continue

    if len(points) < 3:
        return jsonify({"metric": metric, "device": device, "points": points,
                        "trend": "unknown", "message": "数据点不足"})

    values = [p["value"] for p in points]

    # 移动平均
    ma = []
    for i in range(len(values)):
        start_idx = max(0, i - window + 1)
        ma.append(round(statistics.mean(values[start_idx:i + 1]), 3))

    # 变化率
    rates = []
    for i in range(1, len(values)):
        if values[i - 1] != 0:
            rates.append(round((values[i] - values[i - 1]) / abs(values[i - 1]) * 100, 3))
        else:
            rates.append(0)

    # 趋势判断（线性回归斜率）
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = statistics.mean(values)
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator != 0 else 0

    stdev_val = statistics.stdev(values) if len(values) > 1 else 1
    if abs(slope) < 0.01 * stdev_val:
        trend_dir = "stable"
    elif slope > 0:
        trend_dir = "rising"
    else:
        trend_dir = "falling"

    for i, p in enumerate(points):
        p["ma"] = ma[i]
        if i > 0 and i - 1 < len(rates):
            p["rate"] = rates[i - 1]

    return jsonify({
        "metric": metric, "device": device, "trend": trend_dir, "slope": round(slope, 4),
        "mean": round(y_mean, 3), "min": round(min(values), 3), "max": round(max(values), 3),
        "range": round(max(values) - min(values), 3), "current": values[-1],
        "change_from_start": round(values[-1] - values[0], 3), "points": points,
    })


@bp.route("/api/analytics/correlation")
@login_required
def analytics_correlation():
    """指标关联性分析 — 计算两组数据的相关系数"""
    metric_a = sanitize_metric(request.args.get("metric_a", "temperature"))
    metric_b = sanitize_metric(request.args.get("metric_b", "vibration"))
    device = sanitize_device(request.args.get("device", "CNC-A01"), required=True)
    minutes = sanitize_int(request.args.get("minutes", "60"))
    project_id = sanitize_project(request.args.get("project_id"))
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    def fetch_series(metric_name):
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric_name}")
          |> filter(fn: (r) => r.machine_id == "{device}")
          {project_filter}
          |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
        '''
        rows = query_influxdb(flux)
        series = []
        for r in rows:
            try:
                series.append({"time": r.get("_time", ""), "value": float(r.get("_value", 0))})
            except (ValueError, TypeError):
                continue
        return series

    series_a = fetch_series(metric_a)
    series_b = fetch_series(metric_b)

    if len(series_a) < 3 or len(series_b) < 3:
        return jsonify({"metric_a": metric_a, "metric_b": metric_b, "device": device,
                        "correlation": 0, "message": "数据点不足"})

    n = min(len(series_a), len(series_b))
    va = [series_a[i]["value"] for i in range(n)]
    vb = [series_b[i]["value"] for i in range(n)]

    mean_a = statistics.mean(va)
    mean_b = statistics.mean(vb)
    std_a = statistics.stdev(va) if len(va) > 1 else 1
    std_b = statistics.stdev(vb) if len(vb) > 1 else 1

    if std_a == 0 or std_b == 0:
        corr = 0
    else:
        cov = sum((va[i] - mean_a) * (vb[i] - mean_b) for i in range(n)) / n
        corr = cov / (std_a * std_b)

    if corr > 0.7:
        interpretation = "强正相关"
    elif corr > 0.3:
        interpretation = "弱正相关"
    elif corr > -0.3:
        interpretation = "无明显关联"
    elif corr > -0.7:
        interpretation = "弱负相关"
    else:
        interpretation = "强负相关"

    return jsonify({
        "metric_a": metric_a, "metric_b": metric_b, "device": device,
        "correlation": round(corr, 4), "interpretation": interpretation,
        "data_points": n, "mean_a": round(mean_a, 3), "mean_b": round(mean_b, 3),
    })


@bp.route("/api/analytics/alerts")
@login_required
def analytics_alerts():
    """实时告警 — 基于阈值的异常检测"""
    alerts = []
    project_id = sanitize_project(request.args.get("project_id"))
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    for metric_name, cfg in ALERT_THRESHOLDS.items():
        flux = f'''
        from(bucket: "factory")
          |> range(start: -5m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric_name}")
          {project_filter}
          |> last()
        '''
        results = query_influxdb(flux)

        for r in results:
            try:
                val = float(r.get("_value", 0))
                machine = r.get("machine_id", "unknown")
                ts = r.get("_time", "")
            except (ValueError, TypeError):
                continue

            if val >= cfg["critical"]:
                alerts.append({
                    "level": "critical", "metric": metric_name, "label": cfg["label"],
                    "device": machine, "value": val, "threshold": cfg["critical"],
                    "unit": cfg["unit"], "time": ts,
                    "message": f'{machine} {cfg["label"]} 达到危险值 {val}{cfg["unit"]}',
                })
            elif val >= cfg["warning"]:
                alerts.append({
                    "level": "warning", "metric": metric_name, "label": cfg["label"],
                    "device": machine, "value": val, "threshold": cfg["warning"],
                    "unit": cfg["unit"], "time": ts,
                    "message": f'{machine} {cfg["label"]} 接近警告值 {val}{cfg["unit"]}',
                })

    level_order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda a: level_order.get(a["level"], 2))

    return jsonify({
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a["level"] == "critical"),
        "warning": sum(1 for a in alerts if a["level"] == "warning"),
        "alerts": alerts,
    })


@bp.route("/api/analytics/anomalies/batch")
@login_required
def analytics_anomalies_batch():
    """批量异常检测 — 一次请求检测多个指标"""
    metrics_str = request.args.get("metrics", "temperature,vibration")
    metrics = [m.strip() for m in metrics_str.split(",") if m.strip()]
    minutes = sanitize_int(request.args.get("minutes", "1440"))
    threshold = sanitize_float(request.args.get("threshold", "2.0"))
    project_id = sanitize_project(request.args.get("project_id"))
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    results = {}
    for metric in metrics:
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric}")
          {project_filter}
          |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
        '''
        rows = query_influxdb(flux)

        if len(rows) < 5:
            results[metric] = {"metric": metric, "anomalies": [], "total_points": len(rows),
                             "anomaly_count": 0, "message": "数据点不足"}
            continue

        values = []
        for r in rows:
            try:
                val = float(r.get("_value", 0))
                ts = r.get("_time", "")
                machine = r.get("machine_id", "")
                values.append({"time": ts, "value": val, "machine_id": machine})
            except (ValueError, TypeError):
                continue

        if not values:
            results[metric] = {"metric": metric, "anomalies": [], "total_points": 0, "anomaly_count": 0}
            continue

        raw_vals = [v["value"] for v in values]
        mean_val = statistics.mean(raw_vals)
        stdev_val = statistics.stdev(raw_vals) if len(raw_vals) > 1 else 0

        anomalies = []
        if stdev_val > 0:
            for v in values:
                z_score = abs(v["value"] - mean_val) / stdev_val
                if z_score > threshold:
                    anomalies.append({
                        "time": v["time"], "value": v["value"],
                        "machine_id": v["machine_id"],
                        "z_score": round(z_score, 3),
                        "deviation": round(v["value"] - mean_val, 3),
                        "severity": "high" if z_score > 3.0 else "medium" if z_score > 2.5 else "low",
                    })

        filtered = [a for a in anomalies if not is_anomaly_acknowledged(metric, a.get("machine_id", ""), a.get("time", ""))]
        results[metric] = {
            "metric": metric, "total_points": len(values),
            "anomaly_count": len(filtered),
            "anomaly_rate": round(len(filtered) / len(values) * 100, 2) if values else 0,
            "mean": round(mean_val, 3), "stdev": round(stdev_val, 3),
            "anomalies": filtered[:50],
        }

    return jsonify({"results": results})


@bp.route("/api/analytics/project_trend_24h")
@login_required
def analytics_project_trend_24h():
    """项目 24h OEE 趋势 — 供首页迷你图使用"""
    project_id = sanitize_project(request.args.get("project_id"))
    if not project_id:
        return jsonify({"project_id": "", "times": [], "values": [], "data_points": 0,
                       "message": "缺少 project_id"})

    flux = f'''
    from(bucket: "factory")
      |> range(start: -24h)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r.project_id == "{project_id}")
      |> filter(fn: (r) => r._field == "oee")
      |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    '''
    rows = query_influxdb(flux)
    if not rows:
        return jsonify({"project_id": project_id, "times": [], "values": [], "data_points": 0})

    values = []
    times = []
    for r in rows:
        try:
            values.append(round(float(r.get("_value", 0)), 1))
            t = r.get("_time", "")
            times.append(t[11:16] if len(t) > 16 else t)
        except (ValueError, TypeError):
            continue

    return jsonify({
        "project_id": project_id,
        "times": times,
        "values": values,
        "data_points": len(values),
    })
