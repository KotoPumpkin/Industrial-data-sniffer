#!/bin/bash
# =============================================================================
# 工业数据采集平台 — 启动脚本
# =============================================================================

set -e

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║         🏭  工业数据采集管理平台 (IDM)                  ║"
echo "  ║         Industrial Data Mining Platform                 ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")/.."

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

echo "🔨 构建镜像..."
docker compose build

echo ""
echo "🚀 启动所有服务..."
docker compose up -d

echo ""
echo "⏳ 等待服务就绪 (30秒)..."
sleep 30

echo ""
echo "📋 服务状态:"
docker compose ps

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ 所有服务已启动！"
echo ""
echo "  📊 Grafana 仪表盘:   http://localhost:3000"
echo "     用户名: admin  密码: admin123"
echo ""
echo "  🗄️ InfluxDB 管理:   http://localhost:8086"
echo "     用户名: admin  密码: admin123456"
echo ""
echo "  🔧 管理后台:        http://localhost:5000"
echo ""
echo "  📡 MQTT Broker:     localhost:1883"
echo ""
echo "  📋 查看日志:        docker compose logs -f"
echo "  🛑 停止服务:        docker compose down"
echo "════════════════════════════════════════════════════════════"
echo ""