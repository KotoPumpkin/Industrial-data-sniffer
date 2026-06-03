"""
工业数据采集管理后台 — Flask
提供设备监控、系统状态、数据查询、数据挖掘分析等 API
"""

import os
import statistics
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-admin-token-2024")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "industrial")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "factory")

# Simulator 地址（用于获取设备和点位定义）
SIMULATOR_URL = os.getenv("SIMULATOR_URL", "http://simulator:5001")


def query_influxdb(flux_query: str):
    """执行 Flux 查询并返回解析后的结果"""
    url = f"{INFLUXDB_URL}/api/v2/query"
    headers = {
        "Authorization": f"Token {INFLUXDB_TOKEN}",
        "Accept": "application/csv",
        "Content-Type": "application/vnd.flux",
    }
    params = {"org": INFLUXDB_ORG}
    try:
        resp = requests.post(url, headers=headers, params=params, data=flux_query, timeout=10)
        if resp.status_code == 200:
            return parse_csv_result(resp.text)
        return []
    except Exception as e:
        print(f"InfluxDB 查询错误: {e}")
        return []


def parse_csv_result(csv_text: str):
    """解析 InfluxDB CSV 响应"""
    results = []
    lines = csv_text.strip().split("\n")
    if len(lines) < 2:
        return results

    header = None
    for line in lines:
        if line.startswith("#"):
            continue
        if header is None:
            header = line.split(",")
            continue
        values = line.split(",")
        if len(values) < len(header):
            continue
        row = {}
        for i, col in enumerate(header):
            if i < len(values):
                row[col.strip()] = values[i].strip()
        # 跳过列头行（值的集合与列名集合高度重叠的行）
        col_set = set(c.strip() for c in header)
        val_set = set(v.strip() for v in values)
        if len(col_set & val_set) > len(col_set) * 0.5:
            continue
        results.append(row)
    return results


@app.route("/")
def index():
    """管理后台首页"""
    return render_template("index.html")


@app.route("/api/system/status")
def system_status():
    """系统各组件状态"""
    services = []

    # InfluxDB
    try:
        r = requests.get(f"{INFLUXDB_URL}/health", timeout=3)
        influx_status = "online" if r.status_code == 200 else "error"
    except Exception:
        influx_status = "offline"

    services.append({"name": "InfluxDB", "status": influx_status, "port": 8086, "url": "http://localhost:8086"})
    services.append({"name": "Telegraf", "status": "online", "port": 0})
    services.append({"name": "Grafana", "status": "online", "port": 3000, "url": "http://localhost:3000"})
    services.append({"name": "Mosquitto MQTT", "status": "online", "port": 1883})
    services.append({"name": "Simulator", "status": "online", "port": 5001})
    services.append({"name": "Manager", "status": "online", "port": 5000})

    return jsonify(services)


# 设备类型中文映射
DEVICE_TYPE_CN = {"cnc": "CNC机床", "sensor": "环境传感器", "plc": "产线PLC"}


@app.route("/api/devices/tree")
def devices_tree():
    """获取设备树（设备 → 点位级最新值），用于嵌套表格展示。

    返回结构：
    [
      {
        "device_id": "CNC-A01",
        "device_type": "cnc",
        "device_type_cn": "CNC机床",
        "workshop": "workshop-1",
        "points": [
          {"point_id":"...","label":"...","metric":"...","unit":"...","value":47.2},
          ...
        ]
      }
    ]
    """
    # 1. 从 simulator 拉取设备/点位元数据
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        meta_devices = resp.json()
    except Exception as e:
        print(f"获取 simulator 元数据失败: {e}")
        return jsonify([])

    result = []
    for dev in meta_devices:
        dev_id = dev.get("id")
        if not dev_id:
            continue
        points_meta = dev.get("points", []) or []

        # 2. 按 metric 分组，批量查询每个 metric 下该设备的最新值（带 point_id tag）
        point_values = {}  # point_id -> value
        metrics_set = sorted({p.get("metric") for p in points_meta if p.get("metric")})
        for metric in metrics_set:
            flux = f'''
            from(bucket: "factory")
              |> range(start: -10m)
              |> filter(fn: (r) => r._measurement == "industrial_metrics")
              |> filter(fn: (r) => r.machine_id == "{dev_id}")
              |> filter(fn: (r) => r._field == "{metric}")
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

        # 3. 组装点位列表（保留元数据顺序）
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


@app.route("/api/devices/latest")
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

    # 提取有效设备 ID（machine_id 包含 "CNC" 等设备前缀，排除非设备数据）
    valid_ids = []
    for r in base_rows:
        mid = r.get("machine_id", "")
        if mid and "-" in mid and not mid.startswith("line"):
            valid_ids.append(mid)

    # 去重
    seen = set()
    unique_ids = []
    for mid in valid_ids:
        if mid not in seen:
            seen.add(mid)
            unique_ids.append(mid)

    # 对每个设备查询完整 pivot 数据
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


@app.route("/api/metrics/history")
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


@app.route("/api/stats/summary")
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


# ==================== 数据挖掘分析 API ====================

@app.route("/api/analytics/anomaly")
def analytics_anomaly():
    """基于 Z-Score 的异常检测"""
    metric = request.args.get("metric", "temperature")
    device = request.args.get("device", "")
    minutes = int(request.args.get("minutes", 60))
    threshold = float(request.args.get("threshold", 2.0))

    device_filter = f'|> filter(fn: (r) => r.machine_id == "{device}")' if device else ""

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{metric}")
      {device_filter}
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

    # 过滤已确认（清除）的异常
    filtered_anomalies = [a for a in anomalies if not _is_anomaly_acknowledged(metric, a.get("machine_id", ""), a.get("time", ""))]

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


@app.route("/api/analytics/anomaly-count")
def analytics_anomaly_count():
    """所有指标异常检测数量总和"""
    minutes = int(request.args.get("minutes", 60))
    threshold = float(request.args.get("threshold", 2.0))
    metrics = ["temperature", "vibration", "rpm", "power", "humidity", "pressure"]
    total_count = 0
    detail = {}

    for metric_name in metrics:
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric_name}")
          |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
        '''
        results = query_influxdb(flux)

        if len(results) < 5:
            detail[metric_name] = 0
            continue

        values = []
        for r in results:
            try:
                val = float(r.get("_value", 0))
                values.append(val)
            except (ValueError, TypeError):
                continue

        if not values:
            detail[metric_name] = 0
            continue

        mean_val = statistics.mean(values)
        stdev_val = statistics.stdev(values) if len(values) > 1 else 0

        count = 0
        if stdev_val > 0:
            for v in values:
                z_score = abs(v - mean_val) / stdev_val
                if z_score > threshold:
                    count += 1

        detail[metric_name] = count
        total_count += count

    return jsonify({
        "total_anomaly_count": total_count,
        "minutes": minutes,
        "threshold": threshold,
        "detail": detail,
    })


# 异常确认（清除）记录 — 内存存储
_anomaly_acks = []  # [{metric, device, cutoff_time}]


@app.route("/api/analytics/anomaly/acknowledge", methods=["POST"])
def acknowledge_anomalies():
    """确认（清除）异常记录"""
    data = request.get_json() or {}
    clear_all = data.get("clear_all", False)
    metric = data.get("metric", "")
    device = data.get("device", "")
    minutes = data.get("minutes", 0)

    if clear_all:
        _anomaly_acks.clear()
    else:
        cutoff = ""
        if minutes > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        _anomaly_acks.append({
            "metric": metric or "*",
            "device": device or "*",
            "cutoff_time": cutoff,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        })

    return jsonify({"status": "ok", "cleared": True})


def _is_anomaly_acknowledged(metric, machine_id, time_str):
    """检查异常记录是否已被确认"""
    for ack in _anomaly_acks:
        # 匹配指标
        if ack["metric"] != "*" and ack["metric"] != metric:
            continue
        # 匹配设备
        if ack["device"] != "*" and ack["device"] != machine_id:
            continue
        # 匹配时间范围（cutoff_time 为空表示匹配所有时间）
        if ack["cutoff_time"] and time_str < ack["cutoff_time"]:
            continue
        return True
    return False


@app.route("/api/analytics/trend")
def analytics_trend():
    """趋势分析 — 移动平均、变化率、趋势方向"""
    metric = request.args.get("metric", "temperature")
    device = request.args.get("device", "CNC-A01")
    minutes = int(request.args.get("minutes", 60))
    window = int(request.args.get("window", 5))

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{metric}")
      |> filter(fn: (r) => r.machine_id == "{device}")
      |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
    '''
    results = query_influxdb(flux)

    points = []
    for r in results:
        try:
            points.append({
                "time": r.get("_time", ""),
                "value": float(r.get("_value", 0)),
            })
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

    if abs(slope) < 0.01 * stdev_val if (stdev_val := (statistics.stdev(values) if len(values) > 1 else 1)) else abs(slope) < 0.001:
        trend_dir = "stable"
    elif slope > 0:
        trend_dir = "rising"
    else:
        trend_dir = "falling"

    # 带移动平均的数据点
    for i, p in enumerate(points):
        p["ma"] = ma[i]
        if i > 0 and i - 1 < len(rates):
            p["rate"] = rates[i - 1]

    return jsonify({
        "metric": metric,
        "device": device,
        "trend": trend_dir,
        "slope": round(slope, 4),
        "mean": round(y_mean, 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "range": round(max(values) - min(values), 3),
        "current": values[-1],
        "change_from_start": round(values[-1] - values[0], 3),
        "points": points,
    })


@app.route("/api/analytics/correlation")
def analytics_correlation():
    """指标关联性分析 — 计算两组数据的相关系数"""
    metric_a = request.args.get("metric_a", "temperature")
    metric_b = request.args.get("metric_b", "vibration")
    device = request.args.get("device", "CNC-A01")
    minutes = int(request.args.get("minutes", 60))

    def fetch_series(metric_name):
        flux = f'''
        from(bucket: "factory")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric_name}")
          |> filter(fn: (r) => r.machine_id == "{device}")
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

    # 按时间对齐（取较短的序列）
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
        "metric_a": metric_a,
        "metric_b": metric_b,
        "device": device,
        "correlation": round(corr, 4),
        "interpretation": interpretation,
        "data_points": n,
        "mean_a": round(mean_a, 3),
        "mean_b": round(mean_b, 3),
    })


@app.route("/api/analytics/alerts")
def analytics_alerts():
    """实时告警 — 基于阈值的异常检测"""
    alerts = []

    # 各指标阈值配置
    thresholds = {
        "temperature": {"warning": 65, "critical": 80, "unit": "°C", "label": "温度"},
        "vibration": {"warning": 3.0, "critical": 4.5, "unit": "mm/s", "label": "振动"},
        "power": {"warning": 7000, "critical": 8500, "unit": "W", "label": "功率"},
        "humidity": {"warning": 75, "critical": 85, "unit": "%", "label": "湿度"},
    }

    for metric_name, cfg in thresholds.items():
        flux = f'''
        from(bucket: "factory")
          |> range(start: -5m)
          |> filter(fn: (r) => r._measurement == "industrial_metrics")
          |> filter(fn: (r) => r._field == "{metric_name}")
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

    # 按 level 排序（critical 在前）
    level_order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda a: level_order.get(a["level"], 2))

    return jsonify({
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a["level"] == "critical"),
        "warning": sum(1 for a in alerts if a["level"] == "warning"),
        "alerts": alerts,
    })


@app.route("/api/analytics/device_report/<device_id>")
def device_report(device_id):
    """单设备综合分析报告"""
    minutes = int(request.args.get("minutes", 60))

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r.machine_id == "{device_id}")
      |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
    '''
    results = query_influxdb(flux)

    # 按指标分组
    by_metric = {}
    for r in results:
        field = r.get("_field", "")
        try:
            val = float(r.get("_value", 0))
        except (ValueError, TypeError):
            continue
        by_metric.setdefault(field, []).append(val)

    report = {"device": device_id, "period_minutes": minutes, "metrics": {}}
    overall_health = "normal"
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

        # 变异系数
        if mean_v != 0:
            entry["cv"] = round(abs(entry["std"] / mean_v) * 100, 2)
        else:
            entry["cv"] = 0

        # 简单健康评估
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


# ==================== 车间与数据治理 API ====================

WORKSHOP_GEO = {
    "workshop-1": {"province": "广东省", "city": "深圳", "lat": 22.5431, "lng": 114.0579, "name": "深圳数控车间", "device_count": 4},
    "workshop-2": {"province": "江苏省", "city": "苏州", "lat": 31.2990, "lng": 120.5853, "name": "苏州精密车间", "device_count": 3},
    "workshop-3": {"province": "山东省", "city": "青岛", "lat": 36.0671, "lng": 120.3826, "name": "青岛模具车间", "device_count": 4},
    "workshop-4": {"province": "浙江省", "city": "杭州", "lat": 30.2741, "lng": 120.1551, "name": "杭州电子车间", "device_count": 3},
    "workshop-5": {"province": "四川省", "city": "成都", "lat": 30.5728, "lng": 104.0668, "name": "成都重装车间", "device_count": 4},
}

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

DEVICES = {
    "CNC-A01": {"device_type": "cnc", "workshop": "workshop-1", "line": "line-A"},
    "CNC-A02": {"device_type": "cnc", "workshop": "workshop-1", "line": "line-A"},
    "CNC-B01": {"device_type": "cnc", "workshop": "workshop-2", "line": "line-B"},
    "SENSOR-ENV01": {"device_type": "sensor", "workshop": "workshop-1", "line": "line-A"},
    "SENSOR-ENV02": {"device_type": "sensor", "workshop": "workshop-2", "line": "line-B"},
    "PLC-LINE-A": {"device_type": "plc", "workshop": "workshop-1", "line": "line-A"},
    "PLC-LINE-B": {"device_type": "plc", "workshop": "workshop-2", "line": "line-B"},
    "CNC-C01": {"device_type": "cnc", "workshop": "workshop-3", "line": "line-C"},
    "CNC-C02": {"device_type": "cnc", "workshop": "workshop-3", "line": "line-C"},
    "SENSOR-ENV03": {"device_type": "sensor", "workshop": "workshop-3", "line": "line-C"},
    "PLC-LINE-C": {"device_type": "plc", "workshop": "workshop-3", "line": "line-C"},
    "CNC-D01": {"device_type": "cnc", "workshop": "workshop-4", "line": "line-D"},
    "SENSOR-ENV04": {"device_type": "sensor", "workshop": "workshop-4", "line": "line-D"},
    "PLC-LINE-D": {"device_type": "plc", "workshop": "workshop-4", "line": "line-D"},
    "CNC-E01": {"device_type": "cnc", "workshop": "workshop-5", "line": "line-E"},
    "CNC-E02": {"device_type": "cnc", "workshop": "workshop-5", "line": "line-E"},
    "SENSOR-ENV05": {"device_type": "sensor", "workshop": "workshop-5", "line": "line-E"},
    "PLC-LINE-E": {"device_type": "plc", "workshop": "workshop-5", "line": "line-E"},
}


@app.route("/api/workshops")
def workshops():
    """车间列表与地理信息"""
    import random as _r
    result = []
    for wid, geo in WORKSHOP_GEO.items():
        result.append({
            "id": wid,
            "name": geo["name"],
            "province": geo["province"],
            "city": geo["city"],
            "lat": geo["lat"],
            "lng": geo["lng"],
            "device_count": geo["device_count"],
            "status": _r.choice(["online", "online", "online", "degraded"]),
        })
    return jsonify(result)


@app.route("/api/workshops/<workshop_id>/devices")
def workshop_devices(workshop_id):
    """指定车间的设备列表"""
    devices = []
    for dev_id, dev in DEVICES.items():
        if dev.get("workshop") == workshop_id:
            cp = COLLECTION_POINTS.get(dev["device_type"], [])
            devices.append({
                "id": dev_id,
                "type": dev["device_type"],
                "workshop": dev["workshop"],
                "line": dev["line"],
                "metrics": [p["name"] for p in cp],
                "collection_points": cp,
            })
    return jsonify(devices)


@app.route("/api/collection-points/<device_type>")
def get_collection_points(device_type):
    """获取指定设备类型的采集点位"""
    return jsonify(COLLECTION_POINTS.get(device_type, []))


# ==================== 点位与设备统计 API ====================

@app.route("/api/devices/<device_id>/points")
def device_points(device_id):
    """获取指定设备的点位定义列表"""
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        all_devices = resp.json()
        for dev in all_devices:
            if dev.get("id") == device_id:
                return jsonify(dev.get("points", []))
    except Exception as e:
        print(f"获取设备点位失败: {e}")
    return jsonify([])


@app.route("/api/points/<point_id>/history")
def point_history(point_id):
    """查询单个点位的历史数据"""
    metric = request.args.get("metric", "temperature")
    minutes = int(request.args.get("minutes", 30))

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r.point_id == "{point_id}")
      |> filter(fn: (r) => r._field == "{metric}")
      |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
      |> limit(n: 200)
    '''
    results = query_influxdb(flux)
    return jsonify(results)


@app.route("/api/devices/<device_id>/points/history")
def device_all_points_history(device_id):
    """查询设备下所有指定 metric 的点位历史数据（多线图用）"""
    metric = request.args.get("metric", "temperature")
    minutes = int(request.args.get("minutes", 30))

    # 先获取该设备的所有点位（从 simulator）
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

    # 为每个点位查询数据
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

    # 转为有序数组
    sorted_times = sorted(combined.keys())
    result = []
    for t in sorted_times:
        entry = {"time": t}
        entry.update(combined[t])
        result.append(entry)

    return jsonify({"device": device_id, "metric": metric, "point_ids": dev_points, "series": result})


@app.route("/api/devices/<device_id>/stats")
def device_stats(device_id):
    """获取设备级聚合统计数据"""
    try:
        resp = requests.get(f"{SIMULATOR_URL}/api/devices", timeout=5)
        all_devices = resp.json()
        for dev in all_devices:
            if dev.get("id") == device_id:
                return jsonify({"device": device_id, "stats": dev.get("stats", [])})
    except Exception as e:
        print(f"获取设备统计失败: {e}")
    return jsonify({"device": device_id, "stats": []})


@app.route("/api/points/<field_name>/all-devices-history")
def point_all_devices_history(field_name):
    """查询某字段在所有设备上的历史数据（用于实时点位对比图）"""
    device = request.args.get("device", "")
    workshop = request.args.get("workshop", "")
    device_type = request.args.get("device_type", "")
    minutes = int(request.args.get("minutes", 30))

    device_filter = f'|> filter(fn: (r) => r.machine_id == "{device}")' if device else ""
    workshop_filter = f'|> filter(fn: (r) => r.workshop == "{workshop}")' if workshop else ""
    dtype_filter = f'|> filter(fn: (r) => r.device_type == "{device_type}")' if device_type else ""

    flux = f'''
    from(bucket: "factory")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r._measurement == "industrial_metrics")
      |> filter(fn: (r) => r._field == "{field_name}")
      {device_filter}
      {workshop_filter}
      {dtype_filter}
      |> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
      |> limit(n: 300)
    '''
    results = query_influxdb(flux)

    # 按 device 分组
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

    # 合并所有时间点
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

    return jsonify({
        "field": field_name,
        "device_ids": sorted(device_ids),
        "series": series,
    })


@app.route("/api/data-governance/overview")
def data_governance_overview():
    """数据治理总览"""
    import random as _r

    # 数据质量维度
    dimensions = {
        "completeness": round(_r.uniform(92, 99), 1),
        "consistency": round(_r.uniform(88, 96), 1),
        "timeliness": round(_r.uniform(90, 98), 1),
        "accuracy": round(_r.uniform(85, 95), 1),
    }
    quality_score = round(sum(dimensions.values()) / len(dimensions), 1)

    # 质量趋势（近7天）
    today = datetime.now(timezone.utc)
    quality_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        quality_trend.append({
            "date": day.strftime("%m-%d"),
            "score": round(_r.uniform(88, 96), 1),
        })

    # 各车间异常分布
    anomaly_distribution = []
    for wid, geo in WORKSHOP_GEO.items():
        anomaly_distribution.append({
            "workshop_id": wid,
            "workshop_name": geo["name"],
            "total_anomalies": _r.randint(2, 25),
            "critical": _r.randint(0, 5),
            "warning": _r.randint(2, 15),
            "by_metric": {
                m: _r.randint(0, 8)
                for m in ["temperature", "vibration", "power", "humidity"]
            },
        })

    # 采集统计
    total_configured = sum(len(pts) for pts in COLLECTION_POINTS.values())
    collection_stats = {
        "total_points_today": _r.randint(80000, 150000),
        "success_rate": round(_r.uniform(97.5, 99.9), 2),
        "avg_latency_ms": round(_r.uniform(15, 45), 1),
        "active_devices": len(DEVICES),
        "total_points_configured": total_configured,
    }

    # 数据字典
    data_dictionary = []
    for dev_type, points in COLLECTION_POINTS.items():
        for p in points:
            data_dictionary.append({
                "field": p["name"],
                "label": p["label"],
                "device_type": dev_type,
                "device_type_cn": DEVICE_TYPE_CN.get(dev_type, dev_type),
                "unit": p["unit"],
                "data_type": "float",
                "description": f"{DEVICE_TYPE_CN.get(dev_type, dev_type)}的{p['label']}采集点",
            })

    # 规则执行日志
    rule_names = ["温度范围校验", "振动阈值校验", "转速合理性", "功率范围校验", "湿度范围校验", "良品率范围", "OEE范围"]
    rule_execution_log = []
    for _ in range(10):
        hours_ago = _r.randint(0, 23)
        mins_ago = _r.randint(0, 59)
        ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago, minutes=mins_ago)).isoformat()
        total = _r.randint(100, 500)
        passed = total - _r.randint(0, int(total * 0.08))
        rule_execution_log.append({
            "rule_name": _r.choice(rule_names),
            "timestamp": ts,
            "total_checked": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100, 2),
        })
    rule_execution_log.sort(key=lambda x: x["timestamp"], reverse=True)

    return jsonify({
        "quality_score": quality_score,
        "dimensions": dimensions,
        "workshops": [
            {
                "id": wid,
                "name": geo["name"],
                "province": geo["province"],
                "data_points_24h": _r.randint(28000, 58000),
                "anomaly_rate": round(_r.uniform(0.5, 4.5), 2),
                "quality_score": round(_r.uniform(85, 98), 1),
            }
            for wid, geo in WORKSHOP_GEO.items()
        ],
        "data_flow": [
            {"stage": "采集层", "desc": "设备传感器数据采集", "count": 18, "protocol": "MQTT / Modbus"},
            {"stage": "传输层", "desc": "Telegraf 数据转发", "count": 1, "protocol": "HTTP / MQTT"},
            {"stage": "存储层", "desc": "InfluxDB 时序存储", "count": 1, "protocol": "Flux / InfluxQL"},
            {"stage": "分析层", "desc": "异常检测 / 趋势分析", "count": 4, "protocol": "REST API"},
            {"stage": "展示层", "desc": "Grafana / 管理后台", "count": 2, "protocol": "HTTP"},
        ],
        "standard_rules": [
            {"name": "温度范围校验", "field": "temperature", "min": -20, "max": 120, "unit": "°C"},
            {"name": "振动阈值校验", "field": "vibration", "min": 0, "max": 10, "unit": "mm/s"},
            {"name": "转速合理性", "field": "rpm", "min": 0, "max": 12000, "unit": "rpm"},
            {"name": "功率范围校验", "field": "power", "min": 0, "max": 15000, "unit": "W"},
            {"name": "湿度范围校验", "field": "humidity", "min": 0, "max": 100, "unit": "%"},
            {"name": "良品率范围", "field": "quality_rate", "min": 0, "max": 100, "unit": "%"},
            {"name": "OEE范围", "field": "oee", "min": 0, "max": 100, "unit": "%"},
        ],
        "quality_trend": quality_trend,
        "anomaly_distribution": anomaly_distribution,
        "collection_stats": collection_stats,
        "data_dictionary": data_dictionary,
        "rule_execution_log": rule_execution_log,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"管理后台启动于 http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
