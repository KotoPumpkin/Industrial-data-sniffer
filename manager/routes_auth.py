"""
用户认证路由 — 登录、注册、登出、管理员用户管理
"""

import time

from flask import Blueprint, jsonify, request, render_template, redirect, url_for, session

from auth import (
    find_user_by_username, verify_password, create_user,
    delete_user, reset_user_password, get_all_users,
    login_user_session, logout_user_session,
    login_required, admin_required,
    validate_password_strength,
)
from logger import get_logger

logger = get_logger(__name__)

bp = Blueprint("auth", __name__)

# ── 简易登录限流（模块级内存，单进程内有效） ──
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW = 60      # 60秒窗口
_LOGIN_MAX_ATTEMPTS = 5  # 最多5次
_LOGIN_COOLDOWN = 300   # 超出后锁定5分钟


# ── 页面路由 ──

@bp.route("/login")
def login_page():
    """登录页面"""
    if session.get("user_id"):
        return redirect(url_for("system.index"))
    return render_template("login.html")


@bp.route("/register")
def register_page():
    """注册页面"""
    if session.get("user_id"):
        return redirect(url_for("system.index"))
    return render_template("register.html")


@bp.route("/admin/users")
@admin_required
def admin_users_page():
    """管理员 — 用户管理页面"""
    return render_template("admin.html")


# ── API 路由 ──

@bp.route("/api/auth/login", methods=["POST"])
def api_login():
    """用户登录（含限流保护）"""
    # ── 限流检查 ──
    client_ip = request.remote_addr or "unknown"
    now = time.time()
    attempts = [t for t in _LOGIN_ATTEMPTS.get(client_ip, []) if now - t < _LOGIN_WINDOW]
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        oldest = min(attempts) if attempts else 0
        remaining = _LOGIN_COOLDOWN - (now - oldest)
        if remaining > 0:
            return jsonify({"error": f"登录尝试过于频繁，请 {int(remaining)} 秒后再试"}), 429
    attempts.append(now)
    _LOGIN_ATTEMPTS[client_ip] = attempts
    # ── end 限流 ──

    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    user = find_user_by_username(username)
    if not user or not verify_password(password, user["password"]):
        logger.warning(f"登录失败: {username}")
        return jsonify({"error": "用户名或密码错误"}), 401

    login_user_session(user)
    logger.info(f"用户登录: {username} ({user['role']})")

    # 检查是否需要强制修改密码
    if user.get("password_change_required"):
        return jsonify({
            "username": user["username"],
            "role": user["role"],
            "redirect": "/",
            "password_change_required": True,
        })

    return jsonify({
        "username": user["username"],
        "role": user["role"],
        "redirect": "/admin/users" if user["role"] == "admin" else "/",
    })


@bp.route("/api/auth/register", methods=["POST"])
def api_register():
    """用户注册"""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or ""

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if len(username) < 2 or len(username) > 32:
        return jsonify({"error": "用户名长度 2–32 个字符"}), 400
    pwd_err = validate_password_strength(password)
    if pwd_err:
        return jsonify({"error": pwd_err}), 400
    if password != confirm:
        return jsonify({"error": "两次密码不一致"}), 400

    user = create_user(username, password, role="user")
    if isinstance(user, str):
        return jsonify({"error": user}), 409

    login_user_session(user)
    return jsonify({"username": user["username"], "role": user["role"], "redirect": "/"})


@bp.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """用户登出"""
    username = session.get("username", "")
    logout_user_session()
    logger.info(f"用户登出: {username}")
    return jsonify({"ok": True})


@bp.route("/api/auth/current")
def api_current_user():
    """获取当前登录用户信息"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False})
    return jsonify({
        "authenticated": True,
        "username": session.get("username", ""),
        "role": session.get("role", ""),
    })


# ── 管理员 API ──

@bp.route("/api/admin/users")
@admin_required
def api_list_users():
    """获取用户列表"""
    return jsonify(get_all_users())


@bp.route("/api/admin/users", methods=["POST"])
@admin_required
def api_create_user():
    """管理员创建用户"""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "user")

    if role not in ("admin", "user"):
        return jsonify({"error": "非法角色"}), 400
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    pwd_err = validate_password_strength(password)
    if pwd_err:
        return jsonify({"error": pwd_err}), 400

    user = create_user(username, password, role=role)
    if isinstance(user, str):
        return jsonify({"error": user}), 409

    return jsonify({"id": user["id"], "username": user["username"], "role": user["role"]}), 201


@bp.route("/api/admin/users/<user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    """删除用户"""
    if user_id == session.get("user_id"):
        return jsonify({"error": "不能删除自己"}), 400
    if delete_user(user_id):
        return jsonify({"ok": True})
    return jsonify({"error": "用户不存在"}), 404


@bp.route("/api/admin/users/<user_id>/reset-password", methods=["POST"])
@admin_required
def api_reset_password(user_id):
    """重置用户密码"""
    data = request.get_json() or {}
    new_password = data.get("password") or ""
    pwd_err = validate_password_strength(new_password)
    if pwd_err:
        return jsonify({"error": pwd_err}), 400
    if reset_user_password(user_id, new_password):
        return jsonify({"ok": True})
    return jsonify({"error": "用户不存在"}), 404
