"""
InfluxDB 查询工具
"""

import os
import requests

from config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG
from logger import get_logger

# TLS 证书验证：生产环境必须验证，开发环境可通过环境变量关闭
_CA_CERT = os.getenv("INFLUXDB_CA_CERT")
_VERIFY_TLS = os.getenv("VERIFY_TLS", "true").lower() not in ("false", "0", "no")

logger = get_logger(__name__)


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
        verify = _CA_CERT if _CA_CERT else _VERIFY_TLS
        resp = requests.post(url, headers=headers, params=params, data=flux_query, timeout=10, verify=verify)
        if resp.status_code == 200:
            return parse_csv_result(resp.text)
        logger.warning(f"InfluxDB 查询返回 {resp.status_code}: {resp.text[:200]}")
        return []
    except Exception as e:
        logger.error(f"InfluxDB 查询错误: {e}")
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
