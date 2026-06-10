# 🏭 Industrial Data Mining — 工业数据采集管理平台

> 基于 **Telegraf + InfluxDB + Grafana (TIG)** 标准时序采集线的工业数据采集与管理平台，配备全栈 Dashboard 前端

## 📐 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  工业设备层   │     │  采集代理层   │     │  数据存储层   │     │  可视化层    │
│  PLC / CNC   │────▶│  Telegraf   │────▶│  InfluxDB   │────▶│  Grafana    │
│  Sensor/MQTT │     │  (多协议)    │     │  (时序数据库) │     │  (仪表盘)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           ▲                                        ▲
                           │                                        │
                    ┌──────┴──────┐                          ┌─────┴─────┐
                    │   MQTT      │                          │ 管理后台   │
                    │  Mosquitto  │                          │  Flask    │
                    └─────────────┘                     ┌────>│  (REST)   │
                                                         │     └───────────┘
                                                         │
                                                ┌────────┴─────────┐
                                                │ React Dashboard │
                                                │ (Vite + ECharts)│
                                                │  (localhost:5173)│
                                                └──────────────────┘
```

## 🚀 快速启动

### 前提条件
- Docker & Docker Compose 已安装
- 可用内存 ≥ 4GB

### 一键启动（后端 + 模拟器）

```bash
# 构建并启动所有 Docker 服务
docker compose up -d --build

# 查看启动状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 启动前端 Dashboard（开发模式）

```bash
cd frontend
npm install
npm run dev
# 浏览器打开 http://localhost:5173
```

### 访问地址

| 服务 | 地址 | 账号 |
|------|------|------|
| **React Dashboard（开发）** | http://localhost:5173 | 登录后使用 |
| **管理后台（Flask）** | http://localhost:5000 | 注册后使用 |
| **Grafana 仪表盘** | http://localhost:3000 | admin / admin123 |
| **InfluxDB 管理** | http://localhost:8086 | admin / admin123456 |
| **MQTT Broker** | localhost:1883 | 匿名访问 |

## 📁 项目结构

```
industrial_data_mining/
├── docker-compose.yml              # Docker 编排（6 个服务）
├── .dockerignore                   # 排除 manager/static 避免覆盖构建产物
│
├── frontend/                       # React Dashboard (Vite + TypeScript)
│   ├── src/
│   │   ├── App.tsx                 # 根组件（Topbar + 路由）
│   │   ├── main.tsx                # 入口
│   │   ├── index.css               # 全局样式 + Tailwind 指令
│   │   ├── echarts-setup.ts        # ECharts 全局注册
│   │   ├── pages/
│   │   │   ├── Home.tsx            # 首页（地图 + KPI + 项目列表）
│   │   │   ├── Project.tsx         # 项目视图（7 个 Tab）
│   │   │   └── tabs/
│   │   │       ├── ProjectOverview.tsx   # 项目概览（趋势图 + 车间卡片）
│   │   │       ├── WorkshopOverview.tsx  # 车间概览
│   │   │       ├── DeviceOverview.tsx    # 设备概览
│   │   │       ├── PointOverview.tsx     # 点位概览
│   │   │       ├── AnalyticsTab          # 数据分析（内置）
│   │   │       ├── GovernanceTab         # 数据治理（内置）
│   │   │       └── ReportsTab            # 报告管理（占位）
│   │   ├── components/
│   │   │   ├── map/ChinaMap.tsx          # 交互式中国地图（ECharts）
│   │   │   ├── navigation/
│   │   │   │   ├── HierarchyNav.tsx      # 面包屑层级导航
│   │   │   │   └── DynamicSidebar.tsx    # 动态侧边栏
│   │   │   ├── home/ProjectRanking.tsx   # 项目排行
│   │   │   └── ui/
│   │   │       ├── StatCard.tsx          # 统计卡片组件
│   │   │       ├── CountUp.tsx           # 数字滚动动画
│   │   │       └── GlassPanel.tsx        # 毛玻璃面板
│   │   ├── api/                         # API 客户端
│   │   ├── store/                       # Zustand 状态管理
│   │   ├── hooks/                       # 自定义 Hook
│   │   └── utils/dashboard.tsx          # 共享工具 + 复用组件
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
│
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
│   ├── routes_*.py                 # API 路由（认证/设备/项目/分析等）
│   ├── static/                     # 构建后的前端产物（Docker 构建时生成）
│   └── templates/                  # Jinja2 模板（登录/注册/管理）
├── scripts/
│   ├── start.sh                    # 启动脚本
│   ├── seed_data.py               # 种子数据脚本
│   └── gen-certs.sh               # 证书生成脚本
├── demo/                           # HTML 原型设计稿
├── PRODUCT.md                      # 产品文档
├── DESIGN.md                       # 设计系统文档
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

### 4. React Dashboard（全栈前端）

基于 **Vite + React + TypeScript + ECharts** 构建的全功能工业监控 Dashboard：

#### 首页（Home）
- 🗺️ **交互式中国地图** — ECharts 地理坐标系，展示全国项目分布、点击进入项目概览
- 📊 **全局 KPI** — 总设备数、在线率、平均 OEE、活跃告警数（带数字滚动动画）
- 🔔 **实时告警跑马灯** — 滚动展示最新告警，按严重级别（Critical/Warning）着色
- 📋 **项目卡片列表** — 每个项目的 OEE、告警数、在线设备（framer-motion 入场动画）
- 📈 **24h 项目效率趋势** — 多线折线图对比各项目 OEE 变化
- 🍩 **设备状态环形图** + **综合健康分**

#### 项目概览（ProjectOverview）
- 6 维 KPI 网格（车间数/设备数/采集点/OEE/产量/良品率）
- 车间趋势对比图 — 每个车间一条线，支持**动态指标切换**（温度/振动/功率/转速/湿度/OEE）
- 设备状态分布环形图
- 车间卡片（3 列）— 点击下钻至车间概览
- 图表数据每隔 15 秒自动轮询刷新（无动画）

#### 车间概览（WorkshopOverview）
- 4 维 KPI（OEE/平均温度/平均振动/平均功率）
- 全宽趋势折线图 + **指标下拉框**
- 设备卡片（2 列），显示状态点、主要指标值

#### 设备概览（DeviceOverview）
- **点位选择器** — 浏览设备所有采集点
- 4 维统计（当前值/24h 均值/峰值/谷值）
- 主趋势图（渐变填充 + dataZoom 滑块）
- 分布直方图（20 分箱）+ 关联散点图
- 雷达图（所有点位 vs 基线）

#### 点位概览（PointOverview）
- 大数值卡片（当前值 + 涨跌指示 + 单位）
- 趋势图 + 异常点叠加
- 5 维统计（均值/最小/最大/标准差/CV）
- 数据表格（时间/值/变化率/异常标记）

#### 导航设计
- 🔗 **面包屑层级导航** — 项目 → 车间 → 设备 → 点位，逐层下钻，点击回退
- 📂 **动态侧边栏** — 根据当前层级显示对应导航菜单
- 🔄 **AnimatePresence** — 页面切换流畅动画

#### 内置分析模块（原管理后台迁移）
- 🔍 **异常检测** — Z-Score 统计检验 + 批量异常列表 + 清空操作
- 📈 **趋势分析** — 线性回归斜率 + 趋势方向判断
- 🔗 **关联分析** — Pearson 相关系数
- 📊 **数据治理** — 质量评分、7 天趋势、维度雷达图、车间质量表格

### 5. 管理后台（Flask）
- REST API 路由（认证/设备/项目/分析/系统/报告/治理）
- Flask login 注册认证系统
- 数据治理 API（质量评分、采集统计、规则执行日志）
- 导出分析报告

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| GET | `/api/system/status` | 系统各组件状态 |
| GET | `/api/projects/overview` | 所有项目概览（含 KPI） |
| GET | `/api/devices/tree?project_id={pid}` | 设备树（按车间分组） |
| GET | `/api/devices/latest` | 所有设备最新数据 |
| GET | `/api/metrics/history?metric=temperature&device=CNC-A01&minutes=30` | 历史数据查询 |
| GET | `/api/metrics/history/batch?metric=temperature&devices=CNC-A01,CNC-A02&minutes=30` | 批量历史查询 |
| GET | `/api/analytics/anomaly?metric=temperature&minutes=60&threshold=2.0` | 异常检测 |
| GET | `/api/analytics/anomalies/batch?metrics=temperature,vibration&minutes=1440` | 批量异常检测 |
| GET | `/api/analytics/trend?device=CNC-A01&metric=temperature&minutes=60` | 趋势分析 |
| GET | `/api/analytics/correlation?device=CNC-A01&metric_a=temperature&metric_b=vibration` | 关联分析 |
| GET | `/api/analytics/alerts` | 实时告警列表 |
| GET | `/api/analytics/device_report/{deviceId}?minutes=60` | 设备分析报告 |
| GET | `/api/analytics/project_trend_24h?project_id={pid}` | 项目 24h 效率趋势 |
| GET | `/api/data-governance/overview?project_id={pid}` | 数据治理概览 |

## 📋 技术栈

### 后端
| 组件 | 版本 | 说明 |
|------|------|------|
| Telegraf | 1.30 | 数据采集引擎 |
| InfluxDB | 2.7 | 时序数据库 |
| Grafana | 10.4 | 可视化平台 |
| Mosquitto | 2.x | MQTT Broker |
| Python | 3.12 | 模拟器 & 管理后台 |
| Flask | 3.0 | Web 框架 |

### 前端 Dashboard
| 组件 | 版本 | 说明 |
|------|------|------|
| React | 18.x | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Vite | 5.x | 构建工具 |
| Tailwind CSS | 3.x | 样式框架 |
| ECharts | 5.x | 图表可视化 |
| Framer Motion | 11.x | 页面动画 |
| Zustand | 4.x | 状态管理 |

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
# 启动后端服务
docker compose up -d --build

# 启动前端（开发模式）
cd frontend && npm run dev

# 前端构建
cd frontend && npm run build

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

## 📝 License

MIT