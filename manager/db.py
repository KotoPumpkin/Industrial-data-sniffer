"""
InfluxDB 查询工具
"""

import requests

from config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG


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
