---
name: 工业数据采集管理平台
description: 控制室级工业数据监控仪表盘，深色主题、玻璃面板、3D 视差地图
colors:
  canvas-deep: "#06080d"
  canvas: "#080b10"
  panel: "#0f1218"
  panel-raised: "#161a22"
  sidebar: "#0c0f14"
  input: "#161a22"
  hover: "#1c2029"
  border: "#232830"
  border-light: "#2d333b"
  blue-primary: "#3b82f6"
  blue-dim: "#1e3a5f"
  green-status: "#34d399"
  green-dark: "#0d3320"
  orange-status: "#fb923c"
  orange-dark: "#3d2410"
  red-status: "#f87171"
  red-dark: "#3b1515"
  cyan-accent: "#22d3ee"
  ink: "#e8eaef"
  ink-muted: "#94a3b8"
  ink-dim: "#64748b"
  map-ocean: "#0a1420"
  map-border: "#1e3048"
  glass-bg: "rgba(10, 14, 22, 0.82)"
  glass-border: "rgba(255, 255, 255, 0.06)"
typography:
  display:
    fontFamily: "Inter, sans-serif"
    fontWeight: 700
  heading:
    fontFamily: "Inter, sans-serif"
    fontWeight: 600
    fontSize: "0.75rem"
    letterSpacing: "0.05em"
    textTransform: "uppercase"
  body:
    fontFamily: "'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif"
    fontSize: "0.875rem"
    lineHeight: "1.6"
  kpi:
    fontFamily: "'Rajdhani', 'DIN', monospace"
    fontWeight: 600
    letterSpacing: "-0.02em"
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  glass-card:
    backgroundColor: "{colors.glass-bg}"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.md}"
    padding: "16px"
  glass-card-hover:
    backgroundColor: "rgba(15, 18, 24, 0.88)"
  button-clear:
    backgroundColor: "rgba(248, 113, 113, 0.15)"
    textColor: "{colors.red-status}"
    rounded: "{rounded.md}"
    padding: "4px 10px"
  button-clear-hover:
    backgroundColor: "rgba(248, 113, 113, 0.25)"
  stat-card:
    backgroundColor: "{colors.glass-bg}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
  sidebar:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.ink-muted}"
  sidebar-active:
    backgroundColor: "#162240"
    textColor: "{colors.ink}"
  dropdown:
    backgroundColor: "#111827"
    rounded: "{rounded.md}"
  table-cell:
    textColor: "{colors.ink}"
    typography: kpi
  nav-header:
    backgroundColor: "#161a22"
    textColor: "{colors.ink}"
    height: "3.2rem"
  scrollbar:
    backgroundColor: "transparent"
    rounded: "{rounded.sm}"
  scrollbar-thumb:
    backgroundColor: "#2a3d55"
    rounded: "{rounded.sm}"
  scrollbar-thumb-hover:
    backgroundColor: "#3d5580"
---

# Design System: 工业数据采集管理平台

## 1. Overview

**Creative North Star: "数据深度"**

这是一个为工业运维控制室设计的仪表盘系统。设计语言立足于数据本身的物理感——3D 视差地图提供了跨越省界的空间纵深，玻璃面板营造出控制台前的仪表分层。深色画布不是风格选择，而是功能需求：发光的数据在近乎黑色的背景下获得最大可读性，就像飞机驾驶舱在夜间飞行中依靠仪表发光而非环境光。

系统刻意保持设计元素的克制：没有渐变色文字、没有大面积毛玻璃堆叠、没有彩色侧边装饰条。每一种颜色承载一个编码含义（绿色 = 正常、橙色 = 异常、红色 = 告警、蓝色 = 项目标记），颜色只出现在需要传达状态的地方。使用频率就是信号。

**Key Characteristics:**
- 深色画布层叠：canvas-deep（#06080d）→ canvas（#080b10）→ panel（#0f1218）→ panel-raised（#161a22），四层递进定义空间层次
- 玻璃面板（glass）不是装饰而是功能层，blur + saturate 让悬浮元素与底层 3D 地图建立深度关系
- Inter 处理标题和标签（紧缩、清晰），Rajdhani 处理数字（工业仪表感），中文字体处理正文
- 3D 视差地图是签名字面，CSS perspective + transform 产生真实空间位移

## 2. Colors

深海暗色调为主画布，四种状态色承担语义编码。灰度阶梯从墨色到浅灰共六个层次，覆盖背景、面板、边框、文字。不使用任何暖色中性调（cream/sand/beige 家族）；画布就是近黑色。

### Primary
- **蓝色主色** (#3b82f6)：项目标记、交互焦点、数据高亮。以大蓝色在地图上标记项目位置，在控制面板中作为数据系列色。用于约 8% 的表面。

### Neutral
- **深画布** (#06080d)：根背景。最深的一层，只有在此之上的发光元素才能建立视觉层次。
- **画布** (#080b10)：页面底色。大多数内容区域的底。
- **面板** (#0f1218)：玻璃面板和卡片的基础。略亮于画布。
- **面板浮起** (#161a22)：header、工具栏。画布层级的最高一层。
- **侧栏** (#0c0f14)：导航栏专用。介于 canvas 和 panel 之间。
- **输入框底** (#161a22)：同 panel-raised，表单元素的底色。
- **悬停** (#1c2029)：交互反馈色，比面板浮起略亮。
- **边框** (#232830)：主边框色。玻璃卡片、分割线。
- **浅边框** (#2d333b)：较亮的边框，低频使用。
- **墨色** (#e8eaef)：正文颜色。在深色背景上达到 ≥8:1 对比度。
- **墨色弱** (#94a3b8)：辅助文字、标签。
- **墨色淡** (#64748b)：提示文字、非活跃状态。

### Status
- **绿色** (#34d399)：正常，在线，达标。仅用于状态指示。
- **橙色** (#fb923c)：异常，警告。在红色出现前的前置信号。
- **红色** (#f87171)：告警，临界，危险。最高紧急度的信号。
- **青色** (#22d3ee)：辅助高亮，罕见使用。

### Map Specific
- **海洋深色** (#0a1420)：ECharts 地图底色。
- **地图边框** (#1e3048)：地图省份描边。

### Named Rules
**The Canvas Depth Rule.** 背景只用四层（canvas-deep / canvas / panel / panel-raised），禁止引入第五层或中间色调。深度通过层的堆叠关系传达，不通过单独的阴影或渐变。

**The No-Warm-Neutral Rule.** 任何带有 40-100° 色相的非零彩度中性色都被禁止。画布是纯黑的（#06080d + 轻微蓝色偏移冷却），不是暖色的。温暖感来自数据的发光，不是来自背景的染色。

## 3. Typography

**Heading Font:** Inter, sans-serif（font-weight: 600, letter-spacing: 0.05em, uppercase）— 标签和小标题的工业紧缩感
**Body Font:** PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif — 中文正文，4px 细滚动条匹配
**KPI Font:** Rajdhani, DIN, monospace（font-weight: 600, letter-spacing: -0.02em）— 数字和数据的仪表感

**Character:** Inter 提供紧缩、高可读性的西文标签；Rajdhani 的窄字体比例给大数字一种仪器读数的精确感；中文字体保证正文在 14px 下清晰。三种字体各有专属职能，不混用，不重叠。

### Hierarchy
- **Heading / Label** (Inter, semibold 600, 0.75rem / 12px, 0.05em tracking, uppercase): 面板标题、表头、操作标签。始终使用 `M`（text-gray-400）。
- **Body** (PingFang SC, 0.875rem / 14px, 1.6 line-height): 正文、说明文字、表格内容。使用 `B`。最大行长 65ch。
- **KPI** (Rajdhani, semibold 600, letter-spacing -0.02em): 统计数据、数值、Z-Score、百分比。使用 `K`。数字是页面上最突出的元素。

### Named Rules
**The Three-Font Cap Rule.** Inter + Rajdhani + 中文字体，这三个就是全部。不引入第四种字体系列。仪表盘不是字体展览，是数据呈现工具。

## 4. Elevation

本系统的深度主要通过**色调递进和空间变换**传达，而非传统的盒阴影。四层画布色调叠层支撑大部分纵深。玻璃面板的 backdrop-filter blur（16px, saturate 1.2）产生悬浮于底层 3D 地图之上的雾面分离感。

3D 视差地图使用 CSS perspective（1800px）+ transform（translate / rotate / scale）产生真实的物理空间位移，使地图内容相对于观察者产生前后深度的错觉。平移和缩放过渡曲线使用 cubic-bezier(0.16, 1, 0.3, 1)，约 600ms。

### Shadow Vocabulary
- **dropdown** (`box-shadow: 0 20px 25px -5px rgba(0,0,0,0.4)`)：下拉面板、弹出菜单。唯一使用显著阴影的场景。
- **glass** (no shadow, border: 1px rgba(255,255,255,0.06))：玻璃卡片在自由状态下没有阴影。分离来自 blur + 微妙的亮边框。
- **map tooltip** (`box-shadow: 0 8px 32px rgba(0,0,0,0.6)`)：地图悬浮窗。大模糊半径，纯黑阴影，让 tooltip 从深色地图背景中浮出。

### Named Rules
**The Flat-by-Default Rule.** 除 dropdown 和 tooltip 外，所有表面在自由状态下都没有盒阴影。深度通过色调和 blur 传达，不需要阴影堆叠。

## 5. Components

### Glass Card
容器的主形态。半透明深色背景 + backdrop-filter 模糊 + 1px 60% 透明度白边框。
- **Corner Style:** 8px（rounded-lg）
- **Background:** rgba(10, 14, 22, 0.82)
- **Backdrop:** blur(16px) saturate(1.2)
- **Border:** 1px rgba(255, 255, 255, 0.06)
- **Internal Padding:** 16px
- 无阴影，自由状态扁平

### Stat Card
统计卡片，继承 Glass Card 样式 + KPI 数字展示。
- **Layout:** px-4 py-3（12px × 16px）
- **Label:** text-xs, text-gray-500, uppercase, Inter semibold
- **Value:** text-2xl, font-kpi, color 由语义决定（蓝=普通、红=告警、绿=在线、橙=异常）

### Buttons
- **清除（Clear）按钮**：bg-red-500/15 + text-red-400，hover 到 bg-red-500/25。小尺寸（px-2.5 py-1），rounded-lg。用于异常清除和多处清空操作。
- **导航按钮**：rounded, px-4 py-2.5, 悬停 bg-[#0e1628]，激活 bg-[#162240] + text-gray-200。

### Dropdown
- **触发器**：flex, gap-1.5, px-2.5 py-1.5, rounded-lg, bg-[#111827], text-xs, text-gray-300
- **面板**：fixed, rounded-lg, bg-[#111827], shadow-xl shadow-black/40, z-[99999]
- **选项**：px-3 py-2, text-xs, 激活项 blue-400 + blue-500/10 bg

### Tables
- **Header:** sticky top-0, bg-[#0a0f18], text-[0.7rem], text-gray-500, uppercase, font-heading
- **Rows:** border-b border-gray-800/30, hover:bg-white/[0.02]
- **Cells:** text-xs, first column left-aligned gray-300 font-body, remaining right-aligned font-kpi text-gray-400

### Navigation
- **Sidebar:** w-52, bg-[#0a0f18], border-r border-[#1a2440]
- **Header:** h-[3.2rem], bg-[#161a22], border-b border-[#232830]

### Scrollbar
自定义 4px 宽滚动条。轨道透明，thumb #2a3d55（hover #3d5580），rounded-2px。

### Map (Signature Component)
3D 视差中国地图，ECharts geo + effectScatter。外层 container 设置 perspective:1800px 作为 3D 基准。内层 map div 跟随鼠标位移做 translateX/Y + rotateX/Y + scale(1.03) 变换。0.6s cubic-bezier 过渡。

## 6. Do's and Don'ts

### Do:
- **Do** 使用四层画布色调（#06080d / #080b10 / #0f1218 / #161a22）建立空间层次，不引入新色
- **Do** 用 Rajdhani 字体显示一切数值数据，Inter 显示一切标签标题
- **Do** 保持 glass 卡片无阴影扁平状态——深度来自 blur 和色调，不是阴影
- **Do** 用颜色编码状态：绿 = 正确、橙 = 注意、红 = 紧急，同一页面上每种状态色不超过对应元素数的 15%

### Don't:
- **Don't** 使用任何暖色调中性背景色（cream / sand / beige / warm-gray），画布必须是深冷色调
- **Don't** 在 glass 卡片上叠加盒阴影——blur + 1px 白边框已经足够定义悬浮感
- **Don't** 引入第四种字体系列——Inter + Rajdhani + 中文字体是上限
- **Don't** 在 glass 卡片上叠加毛玻璃 (backdrop-filter) 超过 2 层——单层即可
- **Don't** 使用渐变文字 (background-clip: text) 或彩色左边框 (>1px) 作为视觉强调
