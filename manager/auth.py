"""
用户认证工具 — bcrypt 密码哈希 + Flask-Login session 管理
"""

import json
import os
import uuid
from datetime import datetime, timezone
from functools import wraps

import bcrypt
from flask import request, session, jsonify, redirect, url_for

from logger import get_logger

logger = get_logger(__name__)

USERS_FILE = os.path.join(os.path.dirname(__file__), "data", "users.json")


# ── 用户数据持久化 ──

def _load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_users(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def _ensure_default_admin():
    """首次启动时创建默认管理员，生成随机密码并强制首次修改"""
    users = _load_users()
    if not any(u.get("role") == "admin" for u in users):
        import secrets
        temp_password = secrets.token_urlsafe(12)
        logger.warning("=" * 60)
        logger.warning(f"  默认管理员账户: admin")
        logger.warning(f"  临时密码: {temp_password}")
        logger.warning(f"  请立即登录修改密码！")
        logger.warning("=" * 60)
        users.append({
            "id": str(uuid.uuid4()),
            "username": "admin",
            "password": hash_password(temp_password),
            "role": "admin",
            "password_change_required": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        _save_users(users)
        logger.info("已创建默认管理员账户 admin（首次登录必须修改密码）")


# ── 密码工具 ──

def hash_password(password: str) -> str:
    """bcrypt 加密哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """密码校验"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── 用户查询 ──

def find_user_by_username(username: str):
    """按用户名查找用户"""
    users = _load_users()
    for u in users:
        if u["username"] == username:
            return u
    return None


def find_user_by_id(user_id: str):
    """按 ID 查找用户"""
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            return u
    return None


def get_all_users():
    """返回所有用户（脱敏）"""
    users = _load_users()
    return [
        {"id": u["id"], "username": u["username"], "role": u["role"],
         "created_at": u.get("created_at", "")}
        for u in users
    ]


def create_user(username: str, password: str, role: str = "user"):
    """创建新用户，返回用户 dict 或错误信息字符串（用户名已存在/密码太弱）"""
    if find_user_by_username(username):
        return "用户名已存在"
    pwd_err = validate_password_strength(password)
    if pwd_err:
        return pwd_err
    users = _load_users()
    user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "password": hash_password(password),
        "role": role,
        "password_change_required": role == "admin",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    users.append(user)
    _save_users(users)
    logger.info(f"新用户注册: {username} ({role})")
    return user


def delete_user(user_id: str):
    """删除用户（不能删自己）"""
    users = _load_users()
    new_users = [u for u in users if u["id"] != user_id]
    if len(new_users) == len(users):
        return False
    _save_users(new_users)
    logger.info(f"用户已删除: {user_id}")
    return True


def reset_user_password(user_id: str, new_password: str):
    """重置用户密码"""
    users = _load_users()
    for u in users:
        if u["id"] == user_id:
            u["password"] = hash_password(new_password)
            _save_users(users)
            logger.info(f"密码已重置: {u['username']}")
            return True
    return False


# ── 密码强度校验 ──

def validate_password_strength(password: str) -> str | None:
    """校验密码强度，返回错误信息字符串或 None（通过）"""
    if len(password) < 8:
        return "密码至少 8 个字符"
    if not any(c.islower() for c in password):
        return "密码必须包含小写字母"
    if not any(c.isupper() for c in password):
        return "密码必须包含大写字母"
    if not any(c.isdigit() for c in password):
        return "密码必须包含数字"
    return None


# ── Session 管理 ──

def login_user_session(user):
    """将用户信息写入 session（先清空防 session fixation）"""
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session.permanent = True


def logout_user_session():
    """清除 session"""
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("role", None)


def get_current_user():
    """从 session 获取当前用户"""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return find_user_by_id(user_id)


# ── 装饰器 ──

def login_required(f):
    """要求登录"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            # API 请求返回 401，页面请求重定向
            if request.path.startswith("/api/"):
                return jsonify({"error": "未登录"}), 401
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """要求管理员角色"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "未登录"}), 401
            return redirect(url_for("auth.login_page"))
        if session.get("role") != "admin":
            return jsonify({"error": "权限不足"}), 403
        return f(*args, **kwargs)
    return decorated


# ── 初始化 ──
_ensure_default_admin()
