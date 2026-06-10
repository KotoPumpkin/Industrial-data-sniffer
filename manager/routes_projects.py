"""
项目级 API：首页地图数据、项目统计
"""

import statistics

from flask import Blueprint, jsonify, request

from auth import login_required
from config import PROJECTS, WORKSHOP_GEO, DEVICES, COLLECTION_POINTS
from db import query_influxdb
from validators import sanitize_project
from anomaly_acks import is_anomaly_acknowledged

bp = Blueprint("projects", __name__)


@bp.route("/api/projects/overview")
@login_required
def projects_overview():
    """首页地图：每个项目的聚合数据"""
    result = []
    for pid, pinfo in PROJECTS.items():
        # 所属车间
        workshops = [w for w in WORKSHOP_GEO.values() if w.get("project_id") == pid]
        # 项目下所有设备
        devs = {did: d for did, d in DEVICES.items() if d["project_id"] == pid}
        # 设备数量
        device_count = len(devs)
        # 在线设备数（查询过去 5 分钟有数据的设备）
        online = 0
        try:
            flux = f'''
            from(bucket: "factory")
              |> range(start: -3m)
              |> filter(fn: (r) => r._measurement == "industrial_metrics")
              |> filter(fn: (r) => r.project_id == "{pid}")
              |> keep(columns: ["machine_id"])
              |> unique(column: "machine_id")
            '''
            rows = query_influxdb(flux)
            online = len(rows)
        except Exception:
            online = 0

        # 活跃告警数
        active_alerts = 0
        try:
            alert_flux = f'''
            from(bucket: "factory")
              |> range(start: -5m)
              |> filter(fn: (r) => r._measurement == "industrial_metrics")
              |> filter(fn: (r) => r.project_id == "{pid}")
              |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration"
                        or r._field == "power" or r._field == "humidity")
              |> last()
            '''
            alert_rows = query_influxdb(alert_flux)
            for r in alert_rows:
                try:
                    val = float(r.get("_value", 0))
                    field = r.get("_field", "")
                    thresholds = {
                        "temperature": 65, "vibration": 3.0,
                        "power": 7000, "humidity": 75,
                    }
                    if field in thresholds and val >= thresholds[field]:
                        active_alerts += 1
                except (ValueError, TypeError):
                    continue
        except Exception:
            active_alerts = 0

        # 产量（所有 PLC 设备 count 值总和）
        production = 0
        try:
            prod_flux = f'''
            from(bucket: "factory")
              |> range(start: -1h)
              |> filter(fn: (r) => r._measurement == "industrial_metrics")
              |> filter(fn: (r) => r.project_id == "{pid}")
              |> filter(fn: (r) => r._field == "count")
              |> last()
            '''
            prod_rows = query_influxdb(prod_flux)
            for r in prod_rows:
                try:
                    production += int(float(r.get("_value", 0)))
                except (ValueError, TypeError):
                    continue
        except Exception:
            production = 0

        # OEE 均值（所有 PLC 设备）
        oee_values = []
        try:
            oee_flux = f'''
            from(bucket: "factory")
              |> range(start: -1h)
              |> filter(fn: (r) => r._measurement == "industrial_metrics")
              |> filter(fn: (r) => r.project_id == "{pid}")
              |> filter(fn: (r) => r._field == "oee")
              |> aggregateWindow(every: 10m, fn: mean, createEmpty: false)
            '''
            for r in query_influxdb(oee_flux):
                try:
                    oee_values.append(float(r.get("_value", 0)))
                except (ValueError, TypeError):
                    continue
        except Exception:
            pass
        oee_avg = round(statistics.mean(oee_values), 1) if oee_values else 0.0

        # 项目中心坐标（车间几何中心）
        lats = [w["lat"] for w in workshops]
        lngs = [w["lng"] for w in workshops]
        center_lat = round(sum(lats) / len(lats), 2) if lats else 30
        center_lng = round(sum(lngs) / len(lngs), 2) if lngs else 110

        result.append({
            "id": pid,
            "name": pinfo["name"],
            "color": pinfo["color"],
            "center_lat": center_lat,
            "center_lng": center_lng,
            "workshop_count": len(workshops),
            "device_count": device_count,
            "point_count": sum(len(COLLECTION_POINTS.get(d.get("device_type", ""), [])) for d in devs.values()),
            "online_devices": online,
            "active_alerts": active_alerts,
            "production_count": production,
            "oee_avg": oee_avg,
        })

    return jsonify(result)


@bp.route("/api/projects/<project_id>/stats")
@login_required
def project_stats(project_id):
    """项目驾驶舱统计卡片数据"""
    project_id = sanitize_project(project_id, required=True)
    devs = {did: d for did, d in DEVICES.items() if d["project_id"] == project_id}

    # 在线设备
    online = 0
    try:
        flux = f'''
        from(bucket: "factory")
          |> range(start: -3m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r.project_id == "{project_id}")
          |> keep(columns: ["machine_id"])
          |> unique(column: "machine_id")
        '''
        rows = query_influxdb(flux)
        online = len(rows)
    except Exception:
        online = 0

    # 活跃告警
    alert_count = 0
    try:
        alert_flux = f'''
        from(bucket: "factory")
          |> range(start: -5m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r.project_id == "{project_id}")
          |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration"
                    or r._field == "power" or r._field == "humidity")
          |> last()
        '''
        for r in query_influxdb(alert_flux):
            try:
                val = float(r.get("_value", 0))
                field = r.get("_field", "")
                thresholds = {"temperature": 65, "vibration": 3.0, "power": 7000, "humidity": 75}
                if field in thresholds and val >= thresholds[field]:
                    alert_count += 1
            except (ValueError, TypeError):
                continue
    except Exception:
        alert_count = 0

    # 异常数量（24h，逐点用 is_anomaly_acknowledged 过滤）
    anomaly_count = 0
    try:
        import statistics as st
        metrics = ["temperature", "vibration", "rpm", "power", "humidity", "pressure"]
        for m in metrics:
            aflux = f'''
            from(bucket: "factory")
              |> range(start: -24h)
              |> filter(fn: (r) => r._measurement == "industrial_metrics")
              |> filter(fn: (r) => r.project_id == "{project_id}")
              |> filter(fn: (r) => r._field == "{m}")
              |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
            '''
            rows = query_influxdb(aflux)
            pts = []
            for r in rows:
                try:
                    pts.append({
                        "value": float(r.get("_value", 0)),
                        "time": r.get("_time", ""),
                        "machine_id": r.get("machine_id", ""),
                    })
                except (ValueError, TypeError):
                    continue
            if len(pts) < 5:
                continue
            vals = [p["value"] for p in pts]
            mean_v = st.mean(vals)
            stdev_v = st.stdev(vals) if len(vals) > 1 else 1
            if stdev_v > 0:
                for p in pts:
                    if abs(p["value"] - mean_v) / stdev_v > 2.0:
                        if not is_anomaly_acknowledged(m, p["machine_id"], p["time"]):
                            anomaly_count += 1
    except Exception:
        anomaly_count = 0

    return jsonify({
        "online_devices": online,
        "active_alerts": alert_count,
        "anomaly_count": anomaly_count,
        "workshop_count": len(set(d["workshop"] for d in devs.values())),
    })
