"""
Flux 查询参数校验 — 防注入 + 白名单
"""

import re
from flask import jsonify

from config import (
    PROJECTS, WORKSHOP_GEO, COLLECTION_POINTS,
    ALERT_THRESHOLDS, STANDARD_RULES, DEVICES,
)

# ── 预计算白名单集合 ──

_ALL_METRICS = set()
for _pts in COLLECTION_POINTS.values():
    for _p in _pts:
        _ALL_METRICS.add(_p["name"])
for _r in STANDARD_RULES:
    _ALL_METRICS.add(_r["field"])
_ALL_METRICS.update(ALERT_THRESHOLDS.keys())

_PROJECT_IDS = set(PROJECTS.keys())
_WORKSHOP_IDS = set(WORKSHOP_GEO.keys())
_DEVICE_IDS = set(DEVICES.keys())
_DEVICE_TYPES = {"cnc", "sensor", "plc"}

# 设备 ID 格式：大写字母 + 数字 + 连字符
_DEVICE_RE = re.compile(r"^[A-Z0-9\-]+$")
# Flux 字符串值：字母 + 数字 + 下划线 + 连字符 + 点号
_FLUX_SAFE_RE = re.compile(r"^[A-Za-z0-9_\-.]+$")


class ValidationError(ValueError):
    """参数校验失败"""
    pass


def sanitize_choice(value, allowed, default=None, name="参数"):
    """白名单校验"""
    if not value:
        return default
    if value not in allowed:
        raise ValidationError(f"非法{name}: {value!r}")
    return value


def sanitize_project(value, required=False):
    """项目 ID 校验"""
    if not value and not required:
        return ""
    if value and value not in _PROJECT_IDS:
        raise ValidationError(f"非法 project_id: {value!r}")
    return value


def sanitize_workshop(value, required=False):
    """车间 ID 校验"""
    if not value and not required:
        return ""
    if value and value not in _WORKSHOP_IDS:
        raise ValidationError(f"非法 workshop: {value!r}")
    return value


def sanitize_device(value, required=False):
    """设备 ID 校验（正则 + 已知设备白名单）"""
    if not value and not required:
        return ""
    if value and not _DEVICE_RE.match(value):
        raise ValidationError(f"非法 device_id: {value!r}")
    if value and value not in _DEVICE_IDS:
        raise ValidationError(f"未知设备: {value!r}")
    return value


def sanitize_metric(value, required=True):
    """指标名校验（白名单）"""
    if not value and not required:
        return ""
    if not value:
        raise ValidationError("metric 参数必填")
    if value not in _ALL_METRICS:
        raise ValidationError(f"非法 metric: {value!r}")
    return value


def sanitize_device_type(value):
    """设备类型校验"""
    if not value:
        return ""
    if value not in _DEVICE_TYPES:
        raise ValidationError(f"非法 device_type: {value!r}")
    return value


def sanitize_int(value, default=60, min_val=1, max_val=10080, name="参数"):
    """整数范围校验（默认最大 7 天 = 10080 分钟）"""
    if not value:
        return default
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{name}必须为整数: {value!r}")
    if n < min_val or n > max_val:
        raise ValidationError(f"{name}范围 {min_val}–{max_val}: {n}")
    return n


def sanitize_float(value, default=2.0, min_val=0.1, max_val=10.0, name="参数"):
    """浮点数范围校验"""
    if not value:
        return default
    try:
        n = float(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{name}必须为数字: {value!r}")
    if n < min_val or n > max_val:
        raise ValidationError(f"{name}范围 {min_val}–{max_val}: {n}")
    return n


def sanitize_flux_string(value, name="参数"):
    """Flux 字符串值通用校验 — 仅允许安全字符"""
    if not value:
        return ""
    if not _FLUX_SAFE_RE.match(value):
        raise ValidationError(f"非法{name}: 含不允许的字符")
    return value


def handle_validation_error(e):
    """返回 400 JSON 响应"""
    resp = jsonify({"error": str(e)})
    resp.status_code = 400
    return resp
