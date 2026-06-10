"""异常确认持久化 — 供 routes_analytics 和 routes_projects 共享"""

import json
import os
import tempfile
import threading
from datetime import datetime, timezone

from config import DEVICES

ACK_FILE = os.path.join(os.path.dirname(__file__), "data", "anomaly_acks.json")
_lock = threading.Lock()


def _load_acks():
    try:
        with open(ACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_acks(acks):
    os.makedirs(os.path.dirname(ACK_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(ACK_FILE), suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(acks, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, ACK_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


_anomaly_acks = _load_acks()


def is_anomaly_acknowledged(metric, machine_id, time_str):
    """检查异常记录是否已被确认"""
    for ack in _anomaly_acks:
        if ack.get("metric", "*") != "*" and ack["metric"] != metric:
            continue
        if ack.get("device", "*") != "*" and ack["device"] != machine_id:
            continue
        dev_info = DEVICES.get(machine_id, {})
        if ack.get("project_id", "*") != "*" and ack["project_id"] != dev_info.get("project_id", ""):
            continue
        if ack.get("workshop", "*") != "*" and ack["workshop"] != dev_info.get("workshop", ""):
            continue
        ct = ack.get("cutoff_time", "")
        if ct:
            is_wildcard = ack.get("metric") == "*" and ack.get("device") == "*"
            if is_wildcard:
                # wildcard ack: cutoff 之前的数据被确认（隐藏），之后的不确认
                if time_str >= ct:
                    continue
            else:
                # 定向 ack (via minutes param): cutoff 之后的数据被确认，之前的不确认
                if time_str < ct:
                    continue
        return True
    return False


def get_cutoff_time():
    """获取最近一次 wildcard ack 的截止时间，无则返回 None"""
    latest = None
    for ack in _anomaly_acks:
        if ack.get("metric") == "*" and ack.get("device") == "*":
            ct = ack.get("cutoff_time", "")
            if ct and (latest is None or ct > latest):
                latest = ct
    return latest


def add_ack(ack_entry):
    """添加一条确认记录并保存（线程安全）"""
    with _lock:
        _anomaly_acks.append(ack_entry)
        _save_acks(_anomaly_acks)


def clear_all_acks():
    """清空全部确认记录并保存（线程安全）"""
    with _lock:
        _anomaly_acks.clear()
        _save_acks(_anomaly_acks)
