"""
设备报告路由：单设备综合报告、历史告警、异常检测、合并趋势
"""

import requests
import statistics
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from config import ALERT_THRESHOLDS, SIMULATOR_URL
from db import query_influxdb
from auth import login_required
from validators import sanitize_device, sanitize_int, sanitize_float, ValidationError

bp = Blueprint("reports", __name__)


@bp.route("/api/analytics/device_report/<device_id>")
@login_required
def device_report(device_id):
    """单设备综合分析报告"""
    device_id = sanitize_device(device_id, required=True)
    minutes = sanitize_int(request.args.get("minutes", "60"))

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r.machine_id == "{device_id}")
      |> filter(fn: (r) => r._field != "status")
      |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
    '''
    results = query_influxdb(flux)

    by_metric = {}
    for r in results:
        field = r.get("_field", "")
        try:
            val = float(r.get("_value", 0))
        except (ValueError, TypeError):
            continue
        by_metric.setdefault(field, []).append(val)

    report = {"device": device_id, "period_minutes": minutes, "metrics": {}}
    health_score = 100

    for metric_name, vals in by_metric.items():
        if not vals:
            continue
        mean_v = statistics.mean(vals)
        entry = {
            "mean": round(mean_v, 3),
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
            "std": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0,
            "count": len(vals),
            "latest": round(vals[-1], 3),
        }
        if mean_v != 0:
            entry["cv"] = round(abs(entry["std"] / mean_v) * 100, 2)
        else:
            entry["cv"] = 0

        if metric_name == "temperature" and mean_v > 65:
            health_score -= 20
        if metric_name == "vibration" and mean_v > 3.0:
            health_score -= 25
        if metric_name == "oee" and mean_v < 70:
            health_score -= 15

        report["metrics"][metric_name] = entry

    health_score = max(0, health_score)
    if health_score >= 80:
        overall_health = "normal"
    elif health_score >= 60:
        overall_health = "warning"
    else:
        overall_health = "critical"

    report["health_score"] = health_score
    report["health_status"] = overall_health
    return jsonify(report)


@bp.route("/api/analytics/device_report/<device_id>/alerts")
@login_required
def device_report_alerts(device_id):
    """设备历史告警记录"""
    device_id = sanitize_device(device_id, required=True)
    minutes = sanitize_int(request.args.get("minutes", "60"))
    metric_labels = {"temperature": "温度", "vibration": "振动", "power": "功率", "humidity": "湿度"}
    alerts = []
    for metric, th in ALERT_THRESHOLDS.items():
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric}")
          |> filter(fn: (r) => r.machine_id == "{device_id}")
          |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
          |> limit(n: 200)
        '''
        results = query_influxdb(flux)
        for r in results:
            try:
                val = float(r.get("_value", 0))
            except (ValueError, TypeError):
                continue
            level = None
            if val >= th["critical"]:
                level = "critical"
            elif val >= th["warning"]:
                level = "warning"
            if level:
                ts = r.get("_time", "")
                alerts.append({
                    "time": ts, "metric": metric,
                    "label": metric_labels.get(metric, metric),
                    "level": level, "value": round(val, 2),
                    "threshold": th["warning"] if level == "warning" else th["critical"],
                    "unit": th["unit"],
                    "message": f"{device_id} {metric_labels.get(metric, metric)} {'达到危险值' if level == 'critical' else '达到警告值'} {round(val, 1)}{th['unit']}",
                })
    alerts.sort(key=lambda x: x.get("time", ""), reverse=True)
    return jsonify({"device_id": device_id, "alerts": alerts[:100], "total": len(alerts)})


@bp.route("/api/analytics/device_report/<device_id>/anomalies")
@login_required
def device_report_anomalies(device_id):
    """设备异常检测记录（标注近30分钟）"""
    device_id = sanitize_device(device_id, required=True)
    minutes = sanitize_int(request.args.get("minutes", "60"))
    threshold = sanitize_float(request.args.get("threshold", "2.0"))
    metrics = ["temperature", "vibration", "rpm", "power", "humidity", "pressure", "feed_rate", "voltage", "current"]
    now_utc = datetime.now(timezone.utc)
    cutoff_30min = (now_utc - timedelta(minutes=30)).isoformat()
    all_anomalies = []

    for metric_name in metrics:
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric_name}")
          |> filter(fn: (r) => r.machine_id == "{device_id}")
          |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
        '''
        results = query_influxdb(flux)
        if len(results) < 5:
            continue
        values = []
        for r in results:
            try:
                val = float(r.get("_value", 0))
                ts = r.get("_time", "")
                values.append({"value": val, "time": ts})
            except (ValueError, TypeError):
                continue
        if not values:
            continue
        raw = [v["value"] for v in values]
        mean_val = statistics.mean(raw)
        stdev_val = statistics.stdev(raw) if len(raw) > 1 else 0
        if stdev_val == 0:
            continue
        for v in values:
            z_score = abs(v["value"] - mean_val) / stdev_val
            if z_score > threshold:
                within_30min = v["time"] >= cutoff_30min
                all_anomalies.append({
                    "time": v["time"], "metric": metric_name,
                    "value": round(v["value"], 2), "z_score": round(z_score, 3),
                    "severity": "high" if z_score > 3.0 else "medium" if z_score > 2.5 else "low",
                    "within_30min": within_30min,
                })

    all_anomalies.sort(key=lambda x: x.get("time", ""), reverse=True)
    recent_count = sum(1 for a in all_anomalies if a["within_30min"])
    return jsonify({
        "device_id": device_id, "anomalies": all_anomalies[:100],
        "total_count": len(all_anomalies), "recent_30min_count": recent_count,
    })


@bp.route("/api/analytics/device_report/<device_id>/combined_trend")
@login_required
def device_report_combined_trend(device_id):
    """设备所有指标合并趋势数据"""
    device_id = sanitize_device(device_id, required=True)
    minutes = sanitize_int(request.args.get("minutes", "60"))
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        sim_devices = resp.json() if resp.status_code == 200 else []
    except:
        sim_devices = []

    device_info = next((d for d in sim_devices if d.get("id") == device_id), None)
    if not device_info:
        return jsonify({"device_id": device_id, "metrics": [], "times": [], "series": {}})

    metrics = list(set(p["metric"] for p in device_info.get("points", [])))
    series = {}
    all_times = set()
    metric_data = {}

    for metric in metrics:
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric}")
          |> filter(fn: (r) => r.machine_id == "{device_id}")
          |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
          |> limit(n: 120)
        '''
        results = query_influxdb(flux)
        data = {}
        for r in results:
            t = r.get("_time", "")
            try:
                v = float(r.get("_value", 0))
                data[t] = v
                all_times.add(t)
            except:
                continue
        metric_data[metric] = data

    sorted_times = sorted(all_times)
    for metric in metrics:
        series[metric] = [metric_data[metric].get(t, None) for t in sorted_times]

    formatted_times = []
    for t in sorted_times:
        try:
            formatted_times.append(t[11:19] if len(t) > 19 else t)
        except:
            formatted_times.append(t)

    return jsonify({
        "device_id": device_id, "metrics": metrics,
        "times": formatted_times, "series": series,
    })


@bp.route("/api/analytics/device_report/<device_id>/full")
@login_required
def device_report_full(device_id):
    """合并设备报告 + 合并趋势（单次请求）"""
    device_id = sanitize_device(device_id, required=True)
    minutes = sanitize_int(request.args.get("minutes", "60"))

    # ── Report (same logic as device_report) ──
    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r.machine_id == "{device_id}")
      |> filter(fn: (r) => r._field != "status")
      |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
    '''
    results = query_influxdb(flux)

    by_metric = {}
    for r in results:
        field = r.get("_field", "")
        try:
            val = float(r.get("_value", 0))
        except (ValueError, TypeError):
            continue
        by_metric.setdefault(field, []).append(val)

    report = {"device": device_id, "period_minutes": minutes, "metrics": {}}
    health_score = 100

    for metric_name, vals in by_metric.items():
        if not vals:
            continue
        mean_v = statistics.mean(vals)
        entry = {
            "mean": round(mean_v, 3),
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
            "std": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0,
            "count": len(vals),
            "latest": round(vals[-1], 3),
        }
        if mean_v != 0:
            entry["cv"] = round(abs(entry["std"] / mean_v) * 100, 2)
        else:
            entry["cv"] = 0

        if metric_name == "temperature" and mean_v > 65:
            health_score -= 20
        if metric_name == "vibration" and mean_v > 3.0:
            health_score -= 25
        if metric_name == "oee" and mean_v < 70:
            health_score -= 15

        report["metrics"][metric_name] = entry

    health_score = max(0, health_score)
    if health_score >= 80:
        overall_health = "normal"
    elif health_score >= 60:
        overall_health = "warning"
    else:
        overall_health = "critical"

    report["health_score"] = health_score
    report["health_status"] = overall_health

    # ── Combined trend (same logic as device_report_combined_trend) ──
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        sim_devices = resp.json() if resp.status_code == 200 else []
    except:
        sim_devices = []

    device_info = next((d for d in sim_devices if d.get("id") == device_id), None)
    if not device_info:
        return jsonify({"report": report, "combined_trend": None})

    metrics = list(set(p["metric"] for p in device_info.get("points", [])))
    series = {}
    all_times = set()
    metric_data = {}

    # Dynamic aggregation: match simulator 1s frequency for short ranges,
    # downscale for longer ranges to keep ~1500 data points
    if minutes <= 30:
        agg_window = "1s"
        agg_limit = 1800
    elif minutes <= 120:
        agg_window = "5s"
        agg_limit = 1440
    elif minutes <= 360:
        agg_window = "15s"
        agg_limit = 1440
    else:
        agg_window = "1m"
        agg_limit = 1440

    for metric in metrics:
        flux_ct = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric}")
          |> filter(fn: (r) => r.machine_id == "{device_id}")
          |> aggregateWindow(every: {agg_window}, fn: mean, createEmpty: false)
          |> limit(n: {agg_limit})
        '''
        results_ct = query_influxdb(flux_ct)
        data = {}
        for r in results_ct:
            t = r.get("_time", "")
            try:
                v = float(r.get("_value", 0))
                data[t] = v
                all_times.add(t)
            except:
                continue
        metric_data[metric] = data

    sorted_times = sorted(all_times)
    for metric in metrics:
        series[metric] = [metric_data[metric].get(t, None) for t in sorted_times]

    formatted_times = []
    for t in sorted_times:
        try:
            formatted_times.append(t[11:19] if len(t) > 19 else t)
        except:
            formatted_times.append(t)

    combined_trend = {
        "device_id": device_id, "metrics": metrics,
        "times": formatted_times, "series": series,
    }

    return jsonify({"report": report, "combined_trend": combined_trend})
