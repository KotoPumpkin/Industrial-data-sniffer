# 仪表盘重构进度与计划

## 目标

将 `Project.tsx` 的前 4 个 Tab（仪表盘/项目总览/设备管理/数据采集）参照 `demo/` 文件夹 HTML 原型重构为：**项目概览、车间概览、设备概览、点位概览**。后 3 个 Tab（数据分析/数据治理/报告管理）保持不变。

---

## 额外要求

1. **所有趋势图支持动态指标切换**：项目概览/车间概览/点位概览的趋势图都通过带动画的下拉框切换指标（温度/振动/功率等），设备概览使用点位选择器切换
2. **图表动画策略**：仅在初次创建或切换指标/Tab 时播放动画，数据轮询刷新时禁用动画（`animation: false`）
3. **命名统一**：所有"项目驾驶舱"改为"项目概览"

---

## 完成进度

| 步骤 | 内容 | 状态 |
|------|------|------|
| Step 1 | 扩展 Zustand Store（新增 `currentWorkshopId`/`currentDeviceId`/`currentPointId`） | ✅ 已完成 |
| Step 2 | 提取共享工具到 `src/utils/dashboard.ts` | ✅ 已完成 |
| Step 3 | 更新 `Project.tsx` 导航（Tab 类型、图标、标签、导入新 Tab） | ✅ 已完成 |
| Step 4 | 实现 `ProjectOverview.tsx`（项目概览） | ✅ 已完成 |
| Step 5 | 实现 `WorkshopOverview.tsx`（车间概览） | ✅ 已完成 |
| Step 6 | 实现 `DeviceOverview.tsx`（设备概览） | ✅ 已完成 |
| Step 7 | 实现 `PointOverview.tsx`（点位概览） | ✅ 已完成 |
| Step 8 | 集成清理 + 构建验证 | ✅ 已完成 |

---

## 已修改的文件

### `src/store/useProjectStore.ts` — ✅ 已完成

新增 3 个导航状态字段和对应 setter，设置项目时级联清空下级状态：

```ts
currentWorkshopId: string | null
currentDeviceId: string | null
currentPointId: string | null
setCurrentWorkshop / setCurrentDevice / setCurrentPoint
```

### `src/utils/dashboard.ts` — ✅ 已新建

从 `Project.tsx` 提取的共享模块，包含：

- **常量**：`H`/`B`/`K`/`M` 样式类、`WORKSHOP_NAMES`/`WORKSHOP_PROJECT` 车间映射、`PROJECT_COLORS`/`PROJECT_NAMES` 项目信息、`METRIC_LABELS`/`METRIC_UNITS` 指标中文名和单位、`REFRESH_OPTS` 刷新间隔
- **工具函数**：`flatDevice`、`deviceStatus`、`projectWorkshops`、`deviceMetrics`、`showToast`、`checkAndToast`
- **共享组件**：`Dropdown`（带 framer-motion 动画下拉框）、`RefreshSel`、`Tbl`（通用表格）、`NavBtn`（侧边栏按钮）
- **ECharts 工具**：`useChart` hook（初始化 + 自动 dispose + resize）

### `src/pages/Project.tsx` — ✅ 已重写

- Tab 类型改为：`'project' | 'workshop' | 'device' | 'point' | 'analytics' | 'governance' | 'reports'`
- 默认 Tab 改为 `'project'`
- 删除旧的 `Dashboard`/`ProjectsTab`/`DevicesTab`/`CollectionTab` 及子组件（`AlertsPanel`/`AnomalyPanel`/`WorkshopStatus`/`WorkshopBrief`）
- 保留 `AnalyticsTab`/`GovernanceTab`/`ReportsTab`（从原文件迁移）
- 导入 4 个新 Tab 组件（`ProjectOverview`/`WorkshopOverview`/`DeviceOverview`/`PointOverview`）
- 导航通过回调函数实现层级下钻（`onNavigate`/`onBack`）

---

## 待实现文件（4 个新 Tab）

### Step 4: `src/pages/tabs/ProjectOverview.tsx` — 项目概览

参照 `02-project.html` 实现：

| 区域 | 内容 |
|------|------|
| 面包屑 | 全国项目地图 / {项目名} |
| KPI 网格（3列×2行） | 车间数、设备数、采集点数、OEE、24h产量、良品率 |
| 趋势图区域 | 全宽趋势折线图（每个车间一条线） + 右上角带动画下拉框，可切换指标 |
| 设备状态环形图 | 环形图（在线/告警/离线） |
| 车间卡片（3列） | 可点击，进入车间概览 |

**API 调用**：
- `GET /api/projects/overview` → 项目 KPI
- `GET /api/devices/tree?project_id={pid}` → 按车间分组计算统计、设备状态分布
- `GET /api/metrics/history?metric={selectedMetric}&device={repDevice}&minutes=1440` → 趋势数据
- `GET /api/analytics/trend?metric={selectedMetric}&device={deviceId}&minutes=1440` → 趋势方向

**下拉框可切换指标**：temperature、vibration、power、rpm、humidity、oee 等

---

### Step 5: `src/pages/tabs/WorkshopOverview.tsx` — 车间概览

参照 `03-workshop.html` 实现：

| 区域 | 内容 |
|------|------|
| 面包屑 | 项目名 / {车间名}（可点击回退） |
| KPI 网格（4列） | OEE、平均温度、平均振动、平均功率 |
| 趋势图区域 | 全宽趋势折线图 + 右上角带动画下拉框，可切换指标 |
| 设备卡片（2列） | 4个设备卡片，显示状态点、名称、类型、主要指标 |

**API 调用**：
- `GET /api/devices/tree?project_id={pid}` → 过滤当前车间设备
- `GET /api/metrics/history?metric={selectedMetric}&device={deviceId}&minutes=1440` → 趋势数据
- `GET /api/analytics/trend?metric={selectedMetric}&device={deviceId}&minutes=1440` → 趋势方向 + 移动平均线

**下拉框可切换指标**（根据设备类型动态生成）：CNC=温度/振动/转速/功率/进给/电压/电流；Sensor=温度/湿度/气压/流量；PLC=产量/不良品/良品率/OEE/节拍

---

### Step 6: `src/pages/tabs/DeviceOverview.tsx` — 设备概览

参照 `03-device.html` 实现：

| 区域 | 内容 |
|------|------|
| 面包屑 | 项目名 / 车间名 / {设备ID} |
| 标题+选择器 | 设备类型色点 + 点位下拉选择器 |
| KPI 网格（4列） | 当前值、24h均值、24h峰值、24h谷值（随选中点位变化） |
| 主趋势图 | 24h时序折线（渐变填充 + dataZoom） |
| 双图并排 | 左：分布直方图（20分箱）；右：关联散点图 |
| 雷达图 | 所有点位当前值 vs 基线对比 |

**API 调用**：
- `GET /api/analytics/device_report/{deviceId}?minutes=1440` → 每个指标的 mean/min/max/std/latest
- `GET /api/analytics/device_report/{deviceId}/combined_trend?minutes=1440` → 所有图表数据源

---

### Step 7: `src/pages/tabs/PointOverview.tsx` — 点位概览

| 区域 | 内容 |
|------|------|
| 面包屑 | 项目 / 车间 / 设备 / {点位名} |
| 大数值卡片 | 当前值 + 涨跌指示 + 单位 |
| 趋势图区域 | 全宽趋势折线图 + 右上角带动画下拉框，可切换同设备其他点位 |
| 统计行 | 均值、最小、最大、标准差、CV、异常数 |
| 数据表格 | 时间、值、变化率、异常标记 |

**API 调用**：
- `GET /api/metrics/history?metric={selectedPoint}&device={deviceId}&minutes=1440` → 趋势数据
- `GET /api/analytics/anomaly?metric={selectedPoint}&device={deviceId}&minutes=1440` → 异常点叠加
- `GET /api/analytics/device_report/{deviceId}` → 统计指标
- `GET /api/analytics/trend?metric={selectedPoint}&device={deviceId}&minutes=1440` → 趋势方向

---

## 技术要点

### 图表动画策略

- **初次创建/切换指标时**：ECharts `setOption` 使用 `animation: true`（默认值）
- **数据轮询刷新时**：`setOption` 第二个参数传 `true`（notMerge），或直接设置 `animation: false`
- 具体实现方式：用 `useRef` 记录是否为首次加载，首次后所有 `setOption` 调用都设 `animation: false`

### 下拉框组件

复用 `src/utils/dashboard.ts` 中的 `Dropdown` 组件，已有 framer-motion 入场动画（scaleY + opacity）。

### 导航层级

```
项目概览 ──点击车间卡片──→ 车间概览 ──点击设备卡片──→ 设备概览 ──点击点位──→ 点位概览
    ↑                         ↑                       ↑                      ↑
    └──── 面包屑回退 ─────────┘──── 面包屑回退 ────────┘──── 面包屑回退 ──────┘
```

通过 Zustand store 的 `setCurrentProject`/`setCurrentWorkshop`/`setCurrentDevice`/`setCurrentPoint` 和 Tab 切换实现。

---

## 验证方式

1. 从首页地图点击任意项目 → 进入项目概览，验证 6 个 KPI、趋势图+指标下拉框、车间卡片
2. 点击车间卡片 → 进入车间概览，验证 4 个 KPI、趋势图+指标下拉框、设备卡片
3. 点击设备卡片 → 进入设备概览，验证点位选择器、4 个统计、4 个图表
4. 从设备概览点击点位 → 进入点位概览，验证趋势图+点位下拉框、统计指标、异常叠加
5. 所有 4 个 Tab 的下拉框切换时有 framer-motion 动画效果，趋势图平滑过渡
6. 每层面包屑的回退链接正常工作
7. 数据分析/数据治理/报告管理 Tab 不受影响
8. `npm run build` 无 TypeScript 错误

---

## Docker 部署修复 (2026-06-08)

| 问题 | 根因 | 修复 |
|------|------|------|
| npm install ECONNRESET | Docker 容器无法访问 npm 官方源（中国网络） | Dockerfile 添加 `npm config set registry https://registry.npmmirror.com` |
| 页面空白（JS/CSS 404） | `COPY manager/ .` 用本地旧 `manager/static/` 覆盖了多阶段构建产出的新 `index.html`，导致 hash 不匹配 | 创建 `.dockerignore`，排除 `manager/static/` |
| 页面空白（字体超时） | `fonts.googleapis.com` 被 GFW 阻断，`<link>` 在 `<head>` 中阻塞渲染 30-60s | 全部替换为 `fonts.lug.ustc.edu.cn`（中科大镜像） |

### 修改文件

- `manager/Dockerfile` — 添加 npm mirror、调整 COPY 顺序
- `.dockerignore` — 新增，排除 `manager/static/`
- `frontend/index.html` — Google Fonts → USTC 镜像
- `manager/templates/login.html` — 同上
- `manager/templates/register.html` — 同上
- `manager/templates/admin.html` — 同上
- `manager/templates/index.html` — 同上

### 当前状态

- `docker compose build --no-cache manager && docker compose up -d` 构建成功
- 全部 6 个容器运行中：`idm_manager`、`idm_influxdb` (healthy)、`idm_telegraf`、`idm_simulator`、`idm_grafana`、`idm_mosquitto`
- 前端静态资源 hash 一致性问题已解决（`.dockerignore` 确保多阶段构建产物不被覆盖）
- 字体从国内镜像加载，页面可正常渲染
