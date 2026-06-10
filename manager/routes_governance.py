"""
车间、项目、数据治理、点位查询路由
"""

import random
import requests
import statistics
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from config import (
    COLLECTION_POINTS, DEVICES, DEVICE_TYPE_CN,
    PROJECTS, WORKSHOP_GEO, SIMULATOR_URL,
    STANDARD_RULES,
)
from db import query_influxdb
from logger import get_logger
from validators import (
    sanitize_project, sanitize_device, sanitize_workshop,
    sanitize_device_type, sanitize_metric, sanitize_int,
    sanitize_flux_string, sanitize_choice, ValidationError,
)
from auth import login_required

logger = get_logger(__name__)

bp = Blueprint("governance", __name__)


# ── 项目与车间 ──

@bp.route("/api/projects")
@login_required
def projects_list():
    """返回所有项目及其关联车间"""
    result = []
    for pid, pinfo in PROJECTS.items():
        workshops = []
        for wid, wgeo in WORKSHOP_GEO.items():
            if wgeo.get("project_id") == pid:
                workshops.append({"id": wid, "name": wgeo["name"], "province": wgeo["province"], "city": wgeo["city"]})
        result.append({"id": pid, "name": pinfo["name"], "color": pinfo["color"], "provinces": pinfo["provinces"], "workshops": workshops})
    return jsonify(result)


@bp.route("/api/workshops")
@login_required
def workshops():
    """车间列表与地理信息"""
    result = []
    for wid, geo in WORKSHOP_GEO.items():
        result.append({
            "id": wid, "name": geo["name"],
            "project_id": geo.get("project_id", ""),
            "province": geo["province"], "city": geo["city"],
            "lat": geo["lat"], "lng": geo["lng"],
            "status": random.choice(["online", "online", "online", "degraded"]),
        })
    return jsonify(result)


@bp.route("/api/workshops/<workshop_id>/devices")
@login_required
def workshop_devices(workshop_id):
    """指定车间的设备列表"""
    workshop_id = sanitize_workshop(workshop_id, required=True)
    devices = []
    for dev_id, dev in DEVICES.items():
        if dev.get("workshop") == workshop_id:
            cp = COLLECTION_POINTS.get(dev["device_type"], [])
            devices.append({
                "id": dev_id, "type": dev["device_type"],
                "workshop": dev["workshop"], "line": dev["line"],
                "metrics": [p["name"] for p in cp], "collection_points": cp,
            })
    return jsonify(devices)


@bp.route("/api/collection-points/<device_type>")
@login_required
def get_collection_points(device_type):
    """获取指定设备类型的采集点位"""
    device_type = sanitize_device_type(device_type, required=True)
    return jsonify(COLLECTION_POINTS.get(device_type, []))


# ── 点位与设备统计 ──

@bp.route("/api/devices/<device_id>/points")
@login_required
def device_points(device_id):
    """获取指定设备的点位定义列表"""
    device_id = sanitize_device(device_id, required=True)
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        all_devices = resp.json()
        for dev in all_devices:
            if dev.get("id") == device_id:
                return jsonify(dev.get("points", []))
    except Exception as e:
        logger.warning("获取设备点位失败: %s", e)
    return jsonify([])


@bp.route("/api/points/<point_id>/history")
@login_required
def point_history(point_id):
    """查询单个点位的历史数据"""
    point_id = sanitize_flux_string(point_id, required=True)
    metric = sanitize_metric(request.args.get("metric", "temperature"), required=True)
    minutes = sanitize_int(request.args.get("minutes", "30"))

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r.point_id == "{point_id}")
      |> filter(fn: (r) => r._field == "{metric}")
      |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
      |> limit(n: 200)
    '''
    return jsonify(query_influxdb(flux))


@bp.route("/api/devices/<device_id>/points/history")
@login_required
def device_all_points_history(device_id):
    """查询设备下所有指定 metric 的点位历史数据（多线图用）"""
    device_id = sanitize_device(device_id, required=True)
    metric = sanitize_metric(request.args.get("metric", "temperature"), required=True)
    minutes = sanitize_int(request.args.get("minutes", "30"))

    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        all_devices = resp.json()
        dev_points = []
        for dev in all_devices:
            if dev.get("id") == device_id:
                dev_points = [p["point_id"] for p in dev.get("points", []) if p.get("metric") == metric]
                break
    except Exception:
        dev_points = []

    if not dev_points:
        return jsonify([])

    combined = {}
    for pid in dev_points:
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r.point_id == "{pid}")
          |> filter(fn: (r) => r._field == "{metric}")
          |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
          |> limit(n: 200)
        '''
        rows = query_influxdb(flux)
        for r in rows:
            t = r.get("_time", "")
            try:
                v = float(r.get("_value", 0))
            except (ValueError, TypeError):
                continue
            if t not in combined:
                combined[t] = {}
            combined[t][pid] = v

    sorted_times = sorted(combined.keys())
    result = [{"time": t, **combined[t]} for t in sorted_times]
    return jsonify({"device": device_id, "metric": metric, "point_ids": dev_points, "series": result})


@bp.route("/api/devices/<device_id>/stats")
@login_required
def device_stats(device_id):
    """获取设备级聚合统计数据"""
    device_id = sanitize_device(device_id, required=True)
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        all_devices = resp.json()
        for dev in all_devices:
            if dev.get("id") == device_id:
                return jsonify({"device": device_id, "stats": dev.get("stats", [])})
    except Exception as e:
        logger.warning("获取设备统计失败: %s", e)
    return jsonify({"device": device_id, "stats": []})


@bp.route("/api/points/<field_name>/all-devices-history")
@login_required
def point_all_devices_history(field_name):
    """查询某字段在所有设备上的历史数据（用于实时点位对比图）"""
    field_name = sanitize_metric(field_name, required=True)
    device = sanitize_device(request.args.get("device"))
    workshop = sanitize_workshop(request.args.get("workshop"))
    device_type = sanitize_device_type(request.args.get("device_type"))
    project_id = sanitize_project(request.args.get("project_id"))
    minutes = sanitize_int(request.args.get("minutes", "60"))

    device_filter = f'|> filter(fn: (r) => r.machine_id == "{device}")' if device else ""
    workshop_filter = f'|> filter(fn: (r) => r.workshop == "{workshop}")' if workshop else ""
    dtype_filter = f'|> filter(fn: (r) => r.device_type == "{device_type}")' if device_type else ""
    project_filter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{field_name}")
      {device_filter}
      {workshop_filter}
      {dtype_filter}
      {project_filter}
      |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
      |> limit(n: 300)
    '''
    results = query_influxdb(flux)

    grouped = {}
    device_ids = set()
    for r in results:
        mid = r.get("machine_id", "unknown")
        t = r.get("_time", "")
        try:
            v = float(r.get("_value", 0))
        except (ValueError, TypeError):
            continue
        device_ids.add(mid)
        grouped.setdefault(mid, {})[t] = v

    all_times = set()
    for dev_data in grouped.values():
        all_times.update(dev_data.keys())
    sorted_times = sorted(all_times)

    series = []
    for t in sorted_times:
        entry = {"time": t}
        for did in device_ids:
            entry[did] = grouped.get(did, {}).get(t, None)
        series.append(entry)

    return jsonify({"field": field_name, "device_ids": sorted(device_ids), "series": series})


# ── 数据治理总览 ──

@bp.route("/api/data-governance/overview")
@login_required
def data_governance_overview():
    """数据治理总览 — 基于 InfluxDB 实时数据计算"""
    project_id = sanitize_project(request.args.get("project_id"))
    pfilter = f'|> filter(fn: (r) => r.project_id == "{project_id}")' if project_id else ""

    # ── 1. 最近24h 各指标总数据量（按车间聚合） ──
    flux_24h = f'''
    from(bucket: "factory")
      |> range(start: -24h)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field != "status")
      {pfilter}
      |> group(columns: ["workshop", "_field"])
      |> count(column: "_value")
    '''
    rows_24h = query_influxdb(flux_24h)

    ws_field_counts = {}
    total_points_24h = 0
    for r in rows_24h:
        ws = r.get("workshop", "")
        fld = r.get("_field", "")
        try:
            cnt = int(float(r.get("_value", 0)))
        except (ValueError, TypeError):
            cnt = 0
        ws_field_counts.setdefault(ws, {})[fld] = cnt
        total_points_24h += cnt

    # ── 2. 最近24h 异常数据（超限检测） ──
    ws_anomaly = {}
    total_anomaly_points = 0
    total_checked_points = 0
    for rule in STANDARD_RULES:
        fld = rule["field"]
        threshold_cfg = {
            "temperature": {"warning": 65, "critical": 80},
            "vibration": {"warning": 3.0, "critical": 4.5},
            "power": {"warning": 7000, "critical": 8500},
            "humidity": {"warning": 75, "critical": 85},
        }.get(fld)
        if threshold_cfg:
            warning_val = threshold_cfg["warning"]
            critical_val = threshold_cfg["critical"]
        else:
            warning_val = rule["max"]
            critical_val = warning_val

        flux_anomaly = f'''
        from(bucket: "factory")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{fld}")
          {pfilter}
          |> group(columns: ["workshop"])
          |> count(column: "_value")
        '''
        total_rows = query_influxdb(flux_anomaly)
        total_by_ws = {}
        for tr in total_rows:
            try:
                total_by_ws[tr.get("workshop", "")] = int(float(tr.get("_value", 0)))
            except (ValueError, TypeError):
                pass

        flux_crit = f'''
        from(bucket: "factory")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{fld}")
          |> filter(fn: (r) => r._value >= {critical_val})
          {pfilter}
          |> group(columns: ["workshop"])
          |> count(column: "_value")
        '''
        crit_rows = query_influxdb(flux_crit)

        flux_warn = f'''
        from(bucket: "factory")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{fld}")
          |> filter(fn: (r) => r._value >= {warning_val} and r._value < {critical_val})
          {pfilter}
          |> group(columns: ["workshop"])
          |> count(column: "_value")
        '''
        warn_rows = query_influxdb(flux_warn)

        crit_by_ws = {}
        for cr in crit_rows:
            try:
                crit_by_ws[cr.get("workshop", "")] = int(float(cr.get("_value", 0)))
            except (ValueError, TypeError):
                pass
        warn_by_ws = {}
        for wr in warn_rows:
            try:
                warn_by_ws[wr.get("workshop", "")] = int(float(wr.get("_value", 0)))
            except (ValueError, TypeError):
                pass

        all_ws = set(list(crit_by_ws.keys()) + list(warn_by_ws.keys()) + list(total_by_ws.keys()))
        for ws in all_ws:
            ws_anomaly.setdefault(ws, {}).setdefault(fld, {"critical": 0, "warning": 0, "total": 0})
            ws_anomaly[ws][fld]["critical"] += crit_by_ws.get(ws, 0)
            ws_anomaly[ws][fld]["warning"] += warn_by_ws.get(ws, 0)
            ws_anomaly[ws][fld]["total"] += total_by_ws.get(ws, 0)
            total_anomaly_points += crit_by_ws.get(ws, 0) + warn_by_ws.get(ws, 0)
            total_checked_points += total_by_ws.get(ws, 0)

    # ── 3. 活跃设备数 ──
    flux_active = f'''
    from(bucket: "factory")
      |> range(start: -24h)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      {pfilter}
      |> group(columns: ["machine_id"])
      |> count(column: "_value")
      |> group()
      |> count(column: "machine_id")
    '''
    active_rows = query_influxdb(flux_active)
    active_devices = 0
    if active_rows:
        try:
            active_devices = int(float(active_rows[0].get("_value", 0)))
        except (ValueError, TypeError):
            active_devices = len(DEVICES)

    # ── 4. 计算质量维度 ──
    project_devices = {did: d for did, d in DEVICES.items() if not project_id or d["project_id"] == project_id}
    expected_points_per_device = sum(len(pts) for pts in COLLECTION_POINTS.values())
    expected_total = len(project_devices) * expected_points_per_device * 86400
    completeness = min(100.0, round(total_points_24h / max(expected_total, 1) * 100, 1)) if expected_total > 0 else 100.0
    consistency = round((1 - total_anomaly_points / max(total_checked_points, 1)) * 100, 1) if total_checked_points > 0 else 100.0

    flux_recent = f'''
    from(bucket: "factory")
      |> range(start: -5m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      {pfilter}
      |> group(columns: ["machine_id"])
      |> last(column: "_value")
      |> group()
      |> count(column: "machine_id")
    '''
    recent_rows = query_influxdb(flux_recent)
    recent_devices = 0
    if recent_rows:
        try:
            recent_devices = int(float(recent_rows[0].get("_value", 0)))
        except (ValueError, TypeError):
            pass
    timeliness = round(recent_devices / max(len(project_devices), 1) * 100, 1)
    accuracy = round((consistency * 0.6 + completeness * 0.4), 1)

    dimensions = {
        "completeness": completeness,
        "consistency": consistency,
        "timeliness": timeliness,
        "accuracy": accuracy,
    }
    quality_score = round(sum(dimensions.values()) / len(dimensions), 1)

    # ── 5. 质量趋势（近7天） ──
    quality_trend = []
    today = datetime.now(timezone.utc)
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime("%m-%d")
        offset_hours = i * 24 + 24
        flux_day = f'''
        from(bucket: "factory")
          |> range(start: -{offset_hours}h, stop: -{offset_hours - 24}h)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field != "status")
          {pfilter}
          |> group()
          |> count(column: "_value")
        '''
        day_rows = query_influxdb(flux_day)
        day_count = 0
        if day_rows:
            try:
                day_count = int(float(day_rows[0].get("_value", 0)))
            except (ValueError, TypeError):
                pass
        day_expected = len(DEVICES) * expected_points_per_device * 86400
        day_score = min(99.0, round(day_count / max(day_expected, 1) * 100, 1)) if day_expected > 0 else 95.0
        if day_count == 0 and i > 0:
            day_score = quality_score
        quality_trend.append({"date": day_str, "score": day_score})

    # ── 6. 各车间质量概览 ──
    workshops = []
    for wid, geo in WORKSHOP_GEO.items():
        if project_id and geo.get("project_id") != project_id:
            continue
        ws_total = sum(ws_field_counts.get(wid, {}).values())
        ws_anomaly_count = 0
        ws_checked = 0
        for fld, info in ws_anomaly.get(wid, {}).items():
            ws_anomaly_count += info["critical"] + info["warning"]
            ws_checked += info.get("total", 0)
        anomaly_rate = round(ws_anomaly_count / max(ws_checked, 1) * 100, 2) if ws_checked > 0 else 0.0
        ws_quality = round((1 - anomaly_rate / 100) * 50 + ws_total / max(expected_total / len(WORKSHOP_GEO), 1) * 50, 1) if expected_total > 0 else 95.0
        ws_quality = min(99.0, max(0, ws_quality))
        workshops.append({
            "id": wid, "name": geo["name"], "province": geo["province"],
            "data_points_24h": ws_total, "anomaly_rate": anomaly_rate,
            "quality_score": ws_quality,
        })

    # ── 7. 异常分布（按车间 × 指标） ──
    anomaly_distribution = []
    for wid, geo in WORKSHOP_GEO.items():
        if project_id and geo.get("project_id") != project_id:
            continue
        dist = ws_anomaly.get(wid, {})
        total_crit = sum(v.get("critical", 0) for v in dist.values())
        total_warn = sum(v.get("warning", 0) for v in dist.values())
        anomaly_distribution.append({
            "workshop_id": wid, "workshop_name": geo["name"],
            "total_anomalies": total_crit + total_warn,
            "critical": total_crit, "warning": total_warn,
            "by_metric": {
                m: dist.get(m, {}).get("critical", 0) + dist.get(m, {}).get("warning", 0)
                for m in ["temperature", "vibration", "power", "humidity"]
            },
        })

    # ── 8. 采集统计 ──
    total_configured = sum(len(pts) for pts in COLLECTION_POINTS.values())
    success_rate = round((1 - total_anomaly_points / max(total_checked_points, 1)) * 100, 2) if total_checked_points > 0 else 99.9

    flux_latency = f'''
    from(bucket: "factory")
      |> range(start: -1m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      {pfilter}
      |> last(column: "_time")
      |> keep(columns: ["_time"])
    '''
    latency_rows = query_influxdb(flux_latency)
    avg_latency = 30.0
    if latency_rows:
        latencies = []
        now_utc = datetime.now(timezone.utc)
        for lr in latency_rows:
            ts_str = lr.get("_time", "")
            try:
                ts_str = ts_str.replace("Z", "+00:00")
                t = datetime.fromisoformat(ts_str)
                latencies.append(abs((now_utc - t).total_seconds() * 1000))
            except Exception:
                pass
        if latencies:
            avg_latency = round(statistics.mean(latencies), 1)

    collection_stats = {
        "total_points_today": total_points_24h,
        "success_rate": success_rate,
        "avg_latency_ms": avg_latency,
        "active_devices": active_devices,
        "total_points_configured": total_configured,
    }

    # ── 9. 规则执行日志 ──
    project_ws_ids = [wid for wid, geo in WORKSHOP_GEO.items() if not project_id or geo.get("project_id") == project_id]
    rule_execution_log = []
    for rule in STANDARD_RULES:
        fld = rule["field"]
        total_for_rule = sum(
            ws_anomaly.get(ws, {}).get(fld, {}).get("total", 0) for ws in project_ws_ids
        )
        anomaly_for_rule = sum(
            ws_anomaly.get(ws, {}).get(fld, {}).get("critical", 0) + ws_anomaly.get(ws, {}).get(fld, {}).get("warning", 0)
            for ws in project_ws_ids
        )
        passed = total_for_rule - anomaly_for_rule
        rule_execution_log.append({
            "rule_name": rule["name"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_checked": total_for_rule,
            "passed": passed,
            "failed": anomaly_for_rule,
            "pass_rate": round(passed / max(total_for_rule, 1) * 100, 2),
        })
    rule_execution_log.sort(key=lambda x: x["pass_rate"])

    # ── 10. 数据字典 ──
    data_dictionary = []
    for dev_type, points in COLLECTION_POINTS.items():
        for p in points:
            data_dictionary.append({
                "field": p["name"], "label": p["label"],
                "device_type": dev_type,
                "device_type_cn": DEVICE_TYPE_CN.get(dev_type, dev_type),
                "unit": p["unit"], "data_type": "float",
                "description": f"{DEVICE_TYPE_CN.get(dev_type, dev_type)}的{p['label']}采集点",
            })

    return jsonify({
        "quality_score": quality_score,
        "dimensions": dimensions,
        "workshops": workshops,
        "data_flow": [
            {"stage": "采集层", "desc": "设备传感器数据采集", "count": len(DEVICES), "protocol": "MQTT / Modbus"},
            {"stage": "传输层", "desc": "Telegraf 数据转发", "count": 1, "protocol": "HTTP / MQTT"},
            {"stage": "存储层", "desc": "InfluxDB 时序存储", "count": 1, "protocol": "Flux / InfluxQL"},
            {"stage": "分析层", "desc": "异常检测 / 趋势分析", "count": 4, "protocol": "REST API"},
            {"stage": "展示层", "desc": "Grafana / 管理后台", "count": 2, "protocol": "HTTP"},
        ],
        "standard_rules": STANDARD_RULES,
        "quality_trend": quality_trend,
        "anomaly_distribution": anomaly_distribution,
        "collection_stats": collection_stats,
        "data_dictionary": data_dictionary,
        "rule_execution_log": rule_execution_log,
    })
