"""
工业数据采集管理后台 — Flask 入口

启动方式：
  本地开发：  python app.py
  Docker：    python -m app
"""

import os
import sys

# 支持直接 python app.py 运行（将当前目录加入 sys.path）
if __name__ == "__main__" and __package__ is None:
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    # 使 from routes_xxx import ... 正常工作
    __package__ = "manager"

from flask import Flask
from flask_cors import CORS

from logger import get_logger
from validators import ValidationError, handle_validation_error

from routes_system import bp as system_bp
from routes_devices import bp as devices_bp
from routes_analytics import bp as analytics_bp
from routes_reports import bp as reports_bp
from routes_governance import bp as governance_bp
from routes_auth import bp as auth_bp
from routes_projects import bp as projects_bp

logger = get_logger("app")


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())

    CORS(app, origins=os.getenv("CORS_ORIGINS", "http://localhost:5000").split(","),
         supports_credentials=True)

    app.register_blueprint(system_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(governance_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)

    # 参数校验错误处理
    app.register_error_handler(ValidationError, handle_validation_error)

    # 未登录 API 返回 401
    @app.errorhandler(401)
    def unauthorized(e):
        from flask import jsonify
        return jsonify({"error": "未登录"}), 401

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"管理后台启动于 http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
