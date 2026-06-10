import { useEffect, useState, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import ChinaMap from '../components/map/ChinaMap';
import CountUp from '../components/ui/CountUp';
import { ProjectOverview, getProjectsOverview } from '../api/projects';
import { useAppStore } from '../store/useProjectStore';
import { H, B, K, useChart, POLL_INTERVAL, PROJECT_REGIONS } from '../utils/dashboard';

/* ── Top Bar: scrolling alerts + KPIs ── */
function TopBar({ projects }: { projects: ProjectOverview[] }) {
  const [alerts, setAlerts] = useState<any[]>([]);
  useEffect(() => {
    const load = () => {
      fetch('/api/analytics/alerts', { credentials: 'include' })
        .then(r => r.json()).then(d => setAlerts(d.alerts || [])).catch(() => {});
    };
    load();
    const t = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(t);
  }, []);

  const totalDevices = projects.reduce((s, p) => s + p.device_count, 0);
  const totalOnline = projects.reduce((s, p) => s + p.online_devices, 0);
  const totalAlerts = projects.reduce((s, p) => s + p.active_alerts, 0);
  const avgOEE = projects.length > 0 ? (projects.reduce((s, p) => s + p.oee_avg, 0) / projects.length) : 0;

  return (
    <div className="h-[5rem] flex-shrink-0 flex items-center justify-between px-10 border-b border-[#232830] bg-[rgba(2,6,23,0.9)]">
      {/* Scrolling alerts */}
      <div className="flex-1 min-w-0 flex-shrink-0">
        <div className={`text-[0.65rem] text-gray-500 uppercase tracking-[0.05em] mb-1 ${H}`}>实时告警</div>
        <div className="overflow-x-auto custom-scroll">
          <div className="flex gap-2 w-max">
            {alerts.length === 0 && (
              <span className={`text-[0.7rem] text-gray-600 ${B}`}>暂无告警</span>
            )}
            {alerts.map((a, i) => (
              <div key={i}
                className={`w-[210px] h-10 flex-shrink-0 flex items-center justify-between px-3 rounded-md text-[0.7rem] whitespace-nowrap ${
                  a.level === 'critical' ? 'bg-red-500/45 text-red-100' : 'bg-orange-400/35 text-orange-100'
                }`}>
                <span className="truncate">{a.message || a.device}</span>
                <span className="ml-2 text-[0.65rem] opacity-80">{a.time ? a.time.slice(11, 16) : ''}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="flex items-center gap-0 flex-shrink-0">
        <KpiBox label="总设备数" value={totalDevices} color="#e8eaef" isNumber />
        <KpiSep />
        <KpiBox label="在线率" value={`${totalDevices > 0 ? (totalOnline / totalDevices * 100).toFixed(0) : 0}%`} color="#34d399" />
        <KpiSep />
        <KpiBox label="平均 OEE" value={`${avgOEE.toFixed(1)}%`} color="#3b82f6" />
        <KpiSep />
        <KpiBox label="活跃告警" value={totalAlerts} color={totalAlerts > 0 ? '#f87171' : '#34d399'} isNumber />
      </div>
    </div>
  );
}

function KpiBox({ label, value, color, isNumber }: { label: string; value: string | number; color: string; isNumber?: boolean }) {
  return (
    <div className="text-center">
      <div className={`text-[0.7rem] text-gray-500 uppercase tracking-[0.04em] ${H}`}>{label}</div>
      {isNumber && typeof value === 'number' ? (
        <CountUp end={value} decimals={0} className={`text-[1.6rem] ${K} tabular-nums`} style={{ color }} />
      ) : (
        <div className={`text-[1.6rem] ${K} tabular-nums`} style={{ color }}>{value}</div>
      )}
    </div>
  );
}

function KpiSep() {
  return <div className="w-px h-7 bg-[#232830] mx-7" />;
}

/* ── Map Widget: donut + health score ── */
function MapWidget({ projects }: { projects: ProjectOverview[] }) {
  const donutRef = useRef<HTMLDivElement>(null);
  const donutChart = useChart(donutRef);
  const donutFirst = useRef(true);
  const totalDevices = projects.reduce((s, p) => s + p.device_count, 0);
  const totalOnline = projects.reduce((s, p) => s + p.online_devices, 0);
  const totalAlerts = projects.reduce((s, p) => s + p.active_alerts, 0);
  const offline = Math.max(0, totalDevices - totalOnline - totalAlerts);
  const health = totalDevices > 0 ? Math.round((totalOnline - totalAlerts) / totalDevices * 100) : 0;

  useEffect(() => {
    if (!donutChart.current || totalDevices === 0) return;
    const data = [
      { value: totalOnline, name: '在线', itemStyle: { color: '#22c55e' } },
      { value: offline, name: '离线', itemStyle: { color: '#64748b' } },
      { value: totalAlerts, name: '告警', itemStyle: { color: '#ef4444' } },
    ];
    if (donutFirst.current) {
      donutChart.current.setOption({
        backgroundColor: '#0a0e18',
        animation: true,
        legend: { show: false },
        tooltip: { show: false },
        series: [{
          type: 'pie', radius: ['55%', '75%'], center: ['50%', '50%'],
          avoidLabelOverlap: false,
          label: { show: false },
          hoverAnimation: false,
          emphasis: {
            scale: false,
            focus: 'self',
            label: { show: false },
          },
          data,
        }],
      }, true);
      donutFirst.current = false;
    } else {
      donutChart.current.setOption({ animationDurationUpdate: 0, series: [{ data }] }, false);
    }
  }, [donutChart, totalDevices, totalOnline, totalAlerts, offline]);

  return (
    <div className="absolute bottom-16 left-3 z-10 flex items-stretch gap-5 px-[18px] py-[14px] bg-[rgba(10,14,22,0.88)] backdrop-blur-[12px] border border-white/5 rounded-[10px]">
      <div className="flex flex-col items-center gap-1.5">
        <div ref={donutRef} style={{ width: 80, height: 80 }} />
        <div className={`text-[0.7rem] text-gray-500 uppercase tracking-[0.05em] ${H}`}>设备状态分布</div>
      </div>
      <div className="w-px bg-[#232830]" />
      <div className="flex flex-col items-center justify-center gap-1">
        <div className={`text-[0.7rem] text-gray-500 uppercase tracking-[0.05em] ${H}`}>综合健康分</div>
        <div className="flex items-baseline gap-0.5">
          <span className={`text-[2.4rem] ${K} text-green-400 leading-none`}>{Math.max(0, health)}</span>
          <span className="text-[0.7rem] text-gray-500">/100</span>
        </div>
      </div>
    </div>
  );
}

/* ── Bottom Bar: per-project OEE ── */
function BottomBar({ projects }: { projects: ProjectOverview[] }) {
  const totalDevices = projects.reduce((s, p) => s + p.device_count, 0);
  const totalOnline = projects.reduce((s, p) => s + p.online_devices, 0);
  const avgOEE = projects.length > 0 ? (projects.reduce((s, p) => s + p.oee_avg, 0) / projects.length) : 0;

  return (
    <div className="absolute bottom-0 left-0 right-[280px] h-[52px] flex items-center gap-0 z-10">
      {projects.map(p => (
        <div key={p.id} className="flex-1 text-center py-2 bg-[rgba(10,14,22,0.9)] border-t border-[#232830]">
          <div className={`text-[1.15rem] ${K}`} style={{ color: p.color }}>{p.oee_avg.toFixed(1)}%</div>
          <div className={`text-[0.6rem] text-gray-500 uppercase tracking-[0.04em]`}>{p.name}</div>
        </div>
      ))}
      <div className="flex-1 text-center py-2 bg-[rgba(10,14,22,0.9)] border-t border-[#232830]">
        <div className={`text-[1.15rem] ${K} text-gray-200`}>{totalDevices > 0 ? (totalOnline / totalDevices * 100).toFixed(0) : 0}%</div>
        <div className="text-[0.6rem] text-gray-500 uppercase tracking-[0.04em]">在线率</div>
      </div>
      <div className="flex-1 text-center py-2 bg-[rgba(10,14,22,0.9)] border-t border-[#232830]">
        <div className={`text-[1.15rem] ${K} text-green-400`}>{avgOEE.toFixed(1)}%</div>
        <div className="text-[0.6rem] text-gray-500 uppercase tracking-[0.04em]">平均OEE</div>
      </div>
    </div>
  );
}

/* ── Left Panel: project cards + mini chart ── */
function LeftPanel({ projects, onProjectClick }: { projects: ProjectOverview[]; onProjectClick: (p: ProjectOverview) => void }) {
  const miniRef = useRef<HTMLDivElement>(null);
  const miniChart = useChart(miniRef);
  const miniFirst = useRef(true);
  const [miniHasData, setMiniHasData] = useState(true);
  const totalDevices = projects.reduce((s, p) => s + p.device_count, 0);
  const totalOnline = projects.reduce((s, p) => s + p.online_devices, 0);
  const totalAlerts = projects.reduce((s, p) => s + p.active_alerts, 0);

  useEffect(() => {
    if (!miniChart.current || projects.length === 0) return;
    const loadTrends = async () => {
      const seriesData = await Promise.all(projects.map(async p => {
        try {
          const r = await fetch(`/api/analytics/project_trend_24h?project_id=${p.id}`, { credentials: 'include' });
          if (!r.ok) return null;
          const d = await r.json();
          if (!d.values || d.values.length < 2) return null;
          return { type: 'line', data: d.values, smooth: true, symbol: 'none', lineStyle: { color: p.color, width: 1.5 } };
        } catch { return null; }
      }));
      const validSeries = seriesData.filter(Boolean);
      if (validSeries.length === 0) { setMiniHasData(false); return; }
      setMiniHasData(true);
      const h: string[] = [];
      for (let i = 23; i >= 0; i--) h.push(i + ':00');
      if (miniFirst.current && miniChart.current) {
        miniChart.current.setOption({
          animation: true,
          grid: { top: 4, right: 4, bottom: 16, left: 28 },
          xAxis: { type: 'category', data: h, axisLabel: { color: '#64748b', fontSize: 7, interval: 5 }, axisLine: { show: false }, axisTick: { show: false } },
          yAxis: { type: 'value', min: 70, max: 100, axisLabel: { color: '#64748b', fontSize: 7 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } } },
          series: validSeries,
        }, true);
        miniFirst.current = false;
      } else if (miniChart.current) {
        miniChart.current.setOption({ animationDurationUpdate: 0, series: validSeries }, false);
      }
    };
    loadTrends();
  }, [miniChart, projects]);

  return (
    <div className="w-[280px] flex-shrink-0 overflow-y-auto px-3 py-3 flex flex-col gap-[10px] border-l border-[#232830]">
      <div className={`text-[0.65rem] text-gray-500 uppercase tracking-[0.08em] mb-1.5 ${H}`}>全国项目概览</div>
      <div className={`text-[1.2rem] text-white ${K}`}>{projects.length}<span className="text-[0.7rem] text-gray-500 ml-1">个项目</span></div>
      <div className={`text-[0.7rem] text-gray-500 -mt-2 mb-1 ${B}`}>{totalDevices} 设备 · {totalOnline} 在线 · {totalAlerts} 告警</div>

      {projects.map((p, i) => (
        <motion.div
          key={p.id}
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.25, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
          onClick={() => onProjectClick(p)}
          className="glass glass-interactive rounded-lg p-3 cursor-pointer"
        >
          <div className={`text-[0.85rem] text-gray-200 mb-1 flex items-center gap-2 ${H}`}>
            <span className="inline-block w-[7px] h-[7px] rounded-[1px] flex-shrink-0" style={{ background: p.color }} />
            {p.name}
          </div>
          <div className={`text-[0.7rem] text-gray-500 mb-2`}>{PROJECT_REGIONS[p.id] || ''}</div>
          <div className="grid grid-cols-3 gap-1.5">
            <div className="text-center">
              <div className={`text-[1rem] ${K}`} style={{ color: p.color }}>{p.oee_avg.toFixed(1)}%</div>
              <div className="text-[0.7rem] text-gray-500 uppercase tracking-[0.03em]">效率</div>
            </div>
            <div className="text-center">
              <div className={`text-[1rem] ${K}`} style={{ color: p.active_alerts > 0 ? '#f87171' : '#34d399' }}>{p.active_alerts}</div>
              <div className="text-[0.7rem] text-gray-500 uppercase tracking-[0.03em]">告警</div>
            </div>
            <div className="text-center">
              <div className={`text-[1rem] ${K} text-gray-200`}>{p.online_devices}</div>
              <div className="text-[0.7rem] text-gray-500 uppercase tracking-[0.03em]">在线</div>
            </div>
          </div>
        </motion.div>
      ))}

      <div className="mt-auto">
        <div className={`text-[0.65rem] text-gray-500 uppercase tracking-[0.08em] mb-1.5 ${H} mt-2`}>24h 项目效率趋势</div>
        <div ref={miniRef} style={{ width: '100%', height: 100 }} />
        {!miniHasData && (
          <div className={`text-[0.65rem] text-gray-600 mt-1 text-center ${B}`}>历史数据不足（需至少30分钟运行时间）</div>
        )}
      </div>
    </div>
  );
}

/* ── Main Page ── */
export default function Home() {
  const [projects, setProjects] = useState<ProjectOverview[]>([]);
  const setCurrentProject = useAppStore((s) => s.setCurrentProject);

  const load = useCallback(async () => {
    try {
      setProjects(await getProjectsOverview());
    } catch (e) {
      console.error('Failed to load projects:', e);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <motion.div
      className="flex flex-col h-[calc(100vh-3.2rem)] overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      <TopBar projects={projects} />

      <div className="flex flex-1 relative overflow-hidden">
        {/* Map area */}
        <div className="flex-1 relative min-w-0">
          <ChinaMap projects={projects} onProjectClick={(p) => setCurrentProject(p.id)} />
          <MapWidget projects={projects} />
          <BottomBar projects={projects} />
        </div>

        {/* Left panel (right side in layout) */}
        <LeftPanel projects={projects} onProjectClick={(p) => setCurrentProject(p.id)} />
      </div>
    </motion.div>
  );
}
