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
from routes_system import bp as system_bp
from routes_devices import bp as devices_bp
from routes_analytics import bp as analytics_bp
from routes_reports import bp as reports_bp
from routes_governance import bp as governance_bp


def create_app():
    app = Flask(__name__)

    app.register_blueprint(system_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(governance_bp)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"管理后台启动于 http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
