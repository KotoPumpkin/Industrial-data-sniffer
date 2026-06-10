import React, { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import echarts from '../echarts-setup';

// ── 无障碍辅助 ──
export const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── 样式常量 ──
export const H = 'font-heading font-semibold';
export const B = 'font-body';
export const K = 'font-kpi font-semibold tracking-tighter';
export const M = 'text-gray-400';

// ── 数据刷新与时间窗口常量 ──
export const POLL_INTERVAL = 1000; // 1s，匹配模拟器频率
export const DATA_WINDOW_MINUTES = 5; // 趋势图可见窗口 5 分钟
export const DATA_FETCH_MINUTES = 30; // 拉取 30 分钟数据供回看
export const TIME_RANGE_OPTS = [
  { value: 15, label: '15分' },
  { value: 30, label: '30分' },
  { value: 60, label: '1时' },
  { value: 360, label: '6时' },
  { value: 1440, label: '24时' },
];

// ── dataZoom 5 分钟默认窗口计算 ──
export function getDataZoomConfig(totalMinutes: number = DATA_FETCH_MINUTES) {
  const startPercent = Math.max(0, 100 - (DATA_WINDOW_MINUTES / totalMinutes * 100));
  return {
    start: startPercent,
    end: 100,
  };
}

// ── 趋势图 dataZoom 预设（inside + slider） ──
export function getTrendDataZoom(totalMinutes: number = DATA_FETCH_MINUTES) {
  const { start, end } = getDataZoomConfig(totalMinutes);
  return [
    { type: 'inside' as const, start, end },
    {
      type: 'slider' as const, start, end,
      height: 20, bottom: 0,
      borderColor: '#232830',
      backgroundColor: '#0a0e18',
      fillerColor: 'rgba(59,130,246,0.15)',
      handleStyle: { color: '#3b82f6' },
      textStyle: { color: '#64748b', fontSize: 9 },
    },
  ];
}

// ── 数据更新专用 setOption（保留 dataZoom 状态） ──
export function updateChartSeries(
  chart: echarts.ECharts | null,
  seriesData: any[],
  xAxisData?: (string | number)[],
) {
  if (!chart) return;
  const opt: any = {
    animation: false,
    animationDuration: 0,
    animationDurationUpdate: 0,
    series: seriesData,
  };
  if (xAxisData !== undefined) {
    opt.xAxis = { data: xAxisData };
  }
  chart.setOption(opt, false); // merge mode — 不覆盖 dataZoom / grid / axes
}

// ── 车间映射 ──
export const WORKSHOP_NAMES: Record<string, string> = {
  'workshop-sz': '深圳数控车间', 'workshop-szh': '苏州精密车间', 'workshop-hz': '杭州电子车间',
  'workshop-qd': '青岛模具车间', 'workshop-tj': '天津装配车间', 'workshop-dl': '大连重工车间',
  'workshop-cd': '成都重装车间', 'workshop-cq': '重庆模具车间', 'workshop-km': '昆明精工车间',
};
export const WORKSHOP_PROJECT: Record<string, string> = {
  'workshop-sz': 'project-huadong', 'workshop-szh': 'project-huadong', 'workshop-hz': 'project-huadong',
  'workshop-qd': 'project-beifang', 'workshop-tj': 'project-beifang', 'workshop-dl': 'project-beifang',
  'workshop-cd': 'project-xinan', 'workshop-cq': 'project-xinan', 'workshop-km': 'project-xinan',
};

// ── 项目颜色 ──
export const PROJECT_COLORS: Record<string, string> = {
  'project-huadong': '#0ea5e9',
  'project-beifang': '#f97316',
  'project-xinan': '#22c55e',
};
export const PROJECT_NAMES: Record<string, string> = {
  'project-huadong': '华东制造基地',
  'project-beifang': '北方工业中心',
  'project-xinan': '西南智造园区',
};
export const PROJECT_REGIONS: Record<string, string> = {
  'project-huadong': '广东 · 江苏 · 浙江',
  'project-beifang': '山东 · 天津 · 辽宁',
  'project-xinan': '四川 · 重庆 · 云南',
};

// ── 指标中文名 ──
export const METRIC_LABELS: Record<string, string> = {
  temperature: '温度', vibration: '振动', rpm: '转速', power: '功率',
  feed_rate: '进给速率', voltage: '电压', current: '电流',
  humidity: '湿度', pressure: '气压', flow_rate: '流量',
  count: '产量', defect_count: '不良品', quality_rate: '良品率', oee: 'OEE', cycle_time: '节拍',
};
export const METRIC_UNITS: Record<string, string> = {
  temperature: '°C', vibration: 'mm/s', rpm: 'rpm', power: 'W',
  feed_rate: 'mm/min', voltage: 'V', current: 'A',
  humidity: '%', pressure: 'bar', flow_rate: 'L/min',
  count: 'pcs', defect_count: 'pcs', quality_rate: '%', oee: '%', cycle_time: 's',
};

// ── 工具函数 ──
export function flatDevice(d: any) {
  const vals: Record<string, number> = {};
  (d.points || []).forEach((p: any) => { if (p.value != null) vals[p.metric] = Number(p.value); });
  return { name: d.device_id || d.id, type: d.device_type || '', workshop: d.workshop || '', ...vals };
}

export function deviceStatus(d: any): 'alarm' | 'warn' | 'ok' {
  if ((d.temperature || 0) > 80 || (d.vibration || 0) > 4.5) return 'alarm';
  if ((d.temperature || 0) > 65 || (d.vibration || 0) > 3.0 || (d.power || 0) > 7000) return 'warn';
  return 'ok';
}

export function projectWorkshops(pid: string | null) {
  return Object.entries(WORKSHOP_NAMES).filter(([k]) => !pid || WORKSHOP_PROJECT[k] === pid);
}

export function deviceMetrics(d: any): string[] {
  const parts: string[] = [];
  if (d.temperature != null) parts.push(`温度 ${d.temperature.toFixed(1)}°C`);
  if (d.vibration != null) parts.push(`振动 ${d.vibration.toFixed(2)} mm/s`);
  if (d.power != null) parts.push(`功率 ${d.power.toFixed(0)}W`);
  if (d.rpm != null) parts.push(`转速 ${d.rpm.toFixed(0)}rpm`);
  if (d.humidity != null) parts.push(`湿度 ${d.humidity.toFixed(1)}%`);
  if (d.pressure != null) parts.push(`气压 ${d.pressure.toFixed(1)}bar`);
  if (d.flow_rate != null) parts.push(`流量 ${d.flow_rate.toFixed(1)} L/min`);
  if (d.quality_rate != null) parts.push(`良率 ${d.quality_rate.toFixed(1)}%`);
  if (d.oee != null) parts.push(`OEE ${d.oee.toFixed(1)}%`);
  if (d.count != null) parts.push(`产量 ${d.count.toFixed(0)}pcs`);
  if (d.defect_count != null) parts.push(`不良 ${d.defect_count.toFixed(0)}pcs`);
  if (d.cycle_time != null) parts.push(`节拍 ${d.cycle_time.toFixed(1)}s`);
  return parts;
}

export function showToast(msg: string, level: 'warn' | 'alarm') {
  const id = 'global-toast';
  let el = document.getElementById(id);
  if (!el) { el = document.createElement('div'); el.id = id; el.className = 'fixed top-16 right-4 z-[999] flex flex-col gap-2 pointer-events-none'; document.body.appendChild(el); }
  const t = document.createElement('div');
  t.className = `glass rounded-lg px-4 py-2.5 text-sm ${level === 'alarm' ? 'text-red-400 border-red-500/30' : 'text-yellow-400 border-yellow-500/30'} border animate-fade-in-up pointer-events-auto`;
  t.style.cssText = 'backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);';
  t.textContent = msg;
  el.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(() => t.remove(), 300); }, 4000);
}

export function checkAndToast(devs: any[]) {
  const alarms = devs.filter(d => deviceStatus(d) === 'alarm');
  const warns = devs.filter(d => deviceStatus(d) === 'warn');
  if (alarms.length) showToast(`${alarms.length}台设备触发告警: ${alarms.map(d => d.name).slice(0, 3).join(', ')}${alarms.length > 3 ? '...' : ''}`, 'alarm');
  else if (warns.length) showToast(`${warns.length}台设备异常: ${warns.map(d => d.name).slice(0, 2).join(', ')}${warns.length > 2 ? '...' : ''}`, 'warn');
}

// ── 下拉选择器 ──
export const REFRESH_OPTS = [
  { value: 1000, label: '1s' }, { value: 5000, label: '5s' }, { value: 15000, label: '15s' }, { value: 60000, label: '1min' },
];

export const Dropdown = React.memo(function Dropdown({ value, opts, onChange, cls, width }: {
  value: any; opts: { value: any; label: string }[]; onChange: (v: any) => void; cls?: string; width?: string;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const ref = useRef<HTMLDivElement>(null);
  const cur = opts.find(o => o.value === value) || opts[0];
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const s = () => setOpen(false);
    document.addEventListener('click', h);
    window.addEventListener('scroll', s, { capture: true });
    return () => { document.removeEventListener('click', h); window.removeEventListener('scroll', s, { capture: true }); };
  }, []);
  const toggle = () => {
    if (!open && ref.current) {
      const r = ref.current.getBoundingClientRect();
      setPos({ top: r.bottom + 4, left: r.left });
    }
    setOpen(!open);
  };
  return (
    <div ref={ref} className={`select-none ${cls || ''}`}>
      <div onClick={toggle} role="button" aria-label="切换选项"
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#111827] text-xs text-gray-300 cursor-pointer hover:bg-[#1a2332] transition-colors">
        <span className={K}>{cur?.label}</span>
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2} className={`w-3 h-3 text-gray-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}><path d="M4 6l4 4 4-4" /></svg>
      </div>
      {open && createPortal(
        <motion.div
          initial={{ opacity: 0, scaleY: 0.92, transformOrigin: 'top' }}
          animate={{ opacity: 1, scaleY: 1 }}
          exit={{ opacity: 0, scaleY: 0.92 }}
          transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
          className={`fixed rounded-lg bg-[#111827] shadow-xl shadow-black/40 z-[99999] overflow-hidden border border-white/5 ${width || 'min-w-[5rem]'}`}
          style={{ top: pos.top, left: pos.left }}>
          {opts.map(o => (
            <div key={String(o.value)} onClick={() => { onChange(o.value); setOpen(false); }}
              className={`px-3 py-2 text-xs cursor-pointer transition-colors duration-150 ${
                o.value === value
                  ? 'text-blue-400 bg-blue-500/10'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.04] active:bg-white/[0.06]'
              }`}>{o.label}</div>
          ))}
        </motion.div>,
        document.body
      )}
    </div>
  );
});

export function RefreshSel({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return <Dropdown value={value} opts={REFRESH_OPTS} onChange={onChange} />;
}

export function TimeRangeSel({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return <Dropdown value={value} opts={TIME_RANGE_OPTS} onChange={onChange} />;
}

// ── 通用表格（含滚动保持） ──
export const Tbl = React.memo(function Tbl({ h, rows }: { h: string[]; rows: { cells: any[]; highlight?: string }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const st = el.scrollTop;
    requestAnimationFrame(() => { el.scrollTop = st; });
  }, [rows]);
  return (
    <div ref={ref} className="max-h-64 overflow-y-auto custom-scroll">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-[#0a0f18]">
          <tr className={`text-gray-500 text-[0.7rem] border-b border-gray-800/50 ${H}`}>
            {h.map((x, i) => <th key={i} className={`py-2 font-semibold ${i === 0 ? 'text-left' : 'text-right'}`}>{x}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-gray-800/30 last:border-0 hover:bg-white/[0.02] transition-colors duration-150">
              {r.cells.map((c: any, j: number) => (
                <td key={j} className={`py-2 text-xs ${j === 0 ? `text-gray-300 ${B}` : `text-right ${K} text-gray-400 tabular-nums`}`}
                  style={j === r.cells.length - 1 && r.highlight ? { color: r.highlight } : {}}
                >{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

// ── 侧边栏导航按钮 ──
export function NavBtn({ act, onClick, label, icon }: { act: boolean; onClick: () => void; label: string; icon: string }) {
  return <div onClick={onClick} className={`flex items-center gap-3 px-4 py-2.5 mx-2 rounded cursor-pointer transition-all duration-200 text-sm select-none ${
    act
      ? 'bg-[#162240] text-gray-200 shadow-[inset_0_1px_0_rgba(59,130,246,0.2)]'
      : 'text-gray-400 hover:text-gray-200 hover:bg-[#0e1628] active:bg-[#111d33]'
  } ${B}`}>
    <svg viewBox="0 0 24 24" fill="currentColor" className={`w-4 h-4 flex-shrink-0 transition-opacity duration-200 ${act ? 'opacity-100' : 'opacity-50 group-hover:opacity-70'}`}><path d={icon} /></svg>{label}
  </div>;
}

// ── ECharts 工具：延迟初始化并返回实例，带自动 dispose ──
export function useChart(containerRef: React.RefObject<HTMLDivElement | null>) {
  const chartRef = useRef<echarts.ECharts | null>(null);
  // Init + resize: re-evaluate when container appears (e.g. aggregate→detail view)
  useEffect(() => {
    if (!containerRef.current) return;
    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current, 'dark');
    }
    const handleResize = () => chartRef.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => { window.removeEventListener('resize', handleResize); };
  });
  // Dispose only on unmount
  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);
  return chartRef;
}
