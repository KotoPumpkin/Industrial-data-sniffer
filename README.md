# 🏭 Industrial Data Mining — 工业数据采集管理平台

> 基于 **Telegraf + InfluxDB + Grafana (TIG)** 标准时序采集线的工业数据采集工具

## 📐 架构概览

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  工业设备层   │     │  采集代理层   │     │  数据存储层   │     │  可视化层    │
│  PLC / CNC   │────▶│  Telegraf   │────▶│  InfluxDB   │────▶│  Grafana    │
│  Sensor/MQTT │     │  (多协议)    │     │  (时序数据库) │     │  (仪表盘)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           ▲                                        ▲
                           │                                        │
                    ┌──────┴──────┐                          ┌─────┴─────┐
                    │   MQTT      │                          │  管理后台  │
                    │  Mosquitto  │                          │  Flask    │
                    └─────────────┘                          └───────────┘
```

## 🚀 快速启动

### 前提条件
- Docker & Docker Compose 已安装
- 可用内存 ≥ 4GB

### 一键启动

```bash
# 构建并启动所有服务
docker compose up -d --build

# 查看启动状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 访问地址

| 服务 | 地址 | 账号 |
|------|------|------|
| **Grafana 仪表盘** | http://localhost:3000 | admin / admin123 |
| **InfluxDB 管理** | http://localhost:8086 | admin / admin123456 |
| **管理后台** | http://localhost:5000 | — |
| **MQTT Broker** | localhost:1883 | 匿名访问 |

## 📁 项目结构

```
industrial_data_mining/
├── docker-compose.yml              # Docker 编排（6 个服务）
├── telegraf/
│   └── telegraf.conf               # 采集配置：MQTT + HTTP + Docker + 系统
├── influxdb/
│   └── init/                       # InfluxDB 初始化脚本
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/            # 自动配置 InfluxDB 数据源
│   │   └── dashboards/             # 自动加载仪表盘
│   └── dashboards/
│       └── industrial_overview.json # 预置工业监控仪表盘
├── mosquitto/
│   └── mosquitto.conf              # MQTT Broker 配置
├── simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── simulator.py                # 工业数据模拟器（MQTT + REST API）
├── manager/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                      # Flask 管理后台
│   └── templates/
│       └── index.html              # 工业控制室风格 UI
├── scripts/
│   └── start.sh                    # 启动脚本
└── README.md
```

## 🔧 核心功能

### 1. 多协议数据采集（Telegraf）
- **MQTT Consumer** — 订阅设备遥测数据
- **HTTP JSON** — REST API 数据拉取
- **Docker** — 容器指标采集
- **系统指标** — CPU / 内存 / 磁盘 / 网络

### 2. 工业数据模拟器
模拟 7 台工业设备，每 3 秒生成真实感数据：

| 设备 | 类型 | 指标 |
|------|------|------|
| CNC-A01, CNC-A02, CNC-B01 | 数控机床 | 温度、振动、转速、功率、进给率、电压、电流 |
| SENSOR-ENV01, SENSOR-ENV02 | 环境传感器 | 温度、湿度、压力、流量 |
| PLC-LINE-A, PLC-LINE-B | 产线 PLC | 产量、不良品、良品率、OEE、节拍时间 |

数据特征：
- 正弦波周期变化（模拟设备启停）
- 高斯噪声（模拟传感器抖动）
- 缓慢漂移（模拟环境变化）
- 5% 概率异常脉冲（模拟偶发故障）

### 3. Grafana 仪表盘
预置 **工业数据采集监控面板**，包含：
- 🌡️ 温度监控（阈值告警：绿 → 黄 → 红）
- 📡 振动监控（mm/s 实时曲线）
- ⚡ 功率监控（瓦特级精度）
- 📊 温度/振动趋势（时序图）
- ⚙️ 主轴转速、液压压力、环境湿度
- 📦 产量统计、不良品数、良品率、OEE

自动 5 秒刷新，默认显示最近 15 分钟数据。

### 4. 管理后台
SCADA 控制室风格 Web 界面：
- 系统服务状态实时监控
- 数据采集管线可视化
- 设备实时数据卡片（点击查看分析报告）
- 快速访问各组件

### 5. 数据挖掘分析

管理后台内置 **4 大分析模块**（基于 Chart.js 可视化）：

| 模块 | 功能 | 算法 |
|------|------|------|
| 🔍 异常检测 | 识别设备异常数据点 | Z-Score 统计检验 |
| 📈 趋势分析 | 指标趋势方向、移动平均、变化率 | 线性回归斜率 |
| 🔗 关联分析 | 两个指标的相关性 | Pearson 相关系数 |
| 🚨 实时告警 | 多指标阈值监控 | 温度/振动/功率/湿度阈值检测 |

每个设备还支持生成 **综合分析报告**（点击设备卡片），包含：
- 各指标的均值、极值、标准差、变异系数
- 设备健康评分（0-100）
- 健康状态判定（正常/警告/危险）

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/system/status` | 系统各组件状态 |
| GET | `/api/devices/latest` | 所有设备最新数据 |
| GET | `/api/metrics/history?metric=temperature&device=CNC-A01&minutes=30` | 历史数据查询 |
| GET | `/api/stats/summary` | 统计摘要 |
| GET | `/api/analytics/anomaly?metric=temperature&minutes=60&threshold=2.0` | 异常检测 |
| GET | `/api/analytics/trend?device=CNC-A01&metric=temperature&minutes=60` | 趋势分析 |
| GET | `/api/analytics/correlation?device=CNC-A01&metric_a=temperature&metric_b=vibration` | 关联分析 |
| GET | `/api/analytics/alerts` | 实时告警列表 |
| GET | `/api/analytics/device_report/CNC-A01?minutes=60` | 设备分析报告 |

## ⚙️ 自定义配置

### 添加新设备
编辑 `simulator/simulator.py`，在 `DEVICES` 字典中添加：

```python
"MY-DEVICE-01": {
    "device_type": "custom",
    "workshop": "workshop-1",
    "line": "line-C",
    "metrics": {
        "temperature": {"base": 40, "range": 10, "noise": 1},
    },
},
```

### 修改采集频率
编辑 `telegraf/telegraf.conf`：
```toml
[agent]
  interval = "5s"    # 采集间隔
  flush_interval = "5s"  # 写入间隔
```

### 修改数据保留期
编辑 `docker-compose.yml`：
```yaml
- DOCKER_INFLUXDB_INIT_RETENTION=30d  # 数据保留天数
```

## 🛠️ 常用命令

```bash
# 启动
docker compose up -d --build

# 停止
docker compose down

# 查看日志
docker compose logs -f telegraf     # Telegraf 日志
docker compose logs -f simulator    # 模拟器日志
docker compose logs -f manager      # 管理后台日志

# 重启某个服务
docker compose restart telegraf

# 完全清理（含数据卷）
docker compose down -v
```

## 📋 技术栈

| 组件 | 版本 | 说明 |
|------|------|------|
| Telegraf | 1.30 | 数据采集引擎 |
| InfluxDB | 2.7 | 时序数据库 |
| Grafana | 10.4 | 可视化平台 |
| Mosquitto | 2.x | MQTT Broker |
| Python | 3.12 | 模拟器 & 管理后台 |
| Flask | 3.0 | Web 框架 |

## 📝 License

MIT