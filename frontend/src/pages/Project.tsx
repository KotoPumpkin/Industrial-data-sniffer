import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store/useProjectStore';
import { useNavigationStore, type TabType } from '../store/navigationStore';
import { useState, useEffect, useRef, useCallback } from 'react';
import { H, B, K, M, METRIC_LABELS, prefersReducedMotion } from '../utils/dashboard';
import DynamicSidebar from '../components/navigation/DynamicSidebar';
import HierarchyNav from '../components/navigation/HierarchyNav';
import ProjectOverview from './tabs/ProjectOverview';
import WorkshopOverview from './tabs/WorkshopOverview';
import DeviceOverview from './tabs/DeviceOverview';
import PointOverview from './tabs/PointOverview';

const LABELS: Record<TabType, string> = {
  projectOverview: '项目概览', workshopOverview: '车间概览',
  deviceOverview: '设备概览', pointOverview: '点位概览',
  analytics: '数据分析', governance: '数据治理', reports: '报告管理',
};

export default function Project() {
  const pid = useAppStore(s => s.currentProjectId);
  const setWid = useAppStore(s => s.setCurrentWorkshop);
  const setDid = useAppStore(s => s.setCurrentDevice);
  const setPtid = useAppStore(s => s.setCurrentPoint);
  const setPageSubtitle = useAppStore(s => s.setPageSubtitle);

  const activeTab = useNavigationStore(s => s.activeTab);
  const drillTo = useNavigationStore(s => s.drillTo);

  useEffect(() => { setPageSubtitle(LABELS[activeTab]); }, [activeTab, setPageSubtitle]);

  // ── Drill-down handlers: update old store + new nav store ──
  const handleNavigateWorkshop = (wsId: string) => {
    setWid(wsId);
    drillTo('workshop');
  };

  const handleNavigateDevice = (devId: string) => {
    setDid(devId);
    drillTo('device');
  };

  const handleNavigatePoint = (metric: string) => {
    setPtid(metric);
    drillTo('point');
  };

  if (!pid) return null;

  return (
    <div className="flex h-[calc(100vh-3.2rem)] bg-[#06080d]">
      {/* ── 侧边栏 ── */}
      <DynamicSidebar />

      {/* ── 内容区 ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 面包屑导航 + 上下文信息 */}
        <HierarchyNav />

        {/* 页面内容 */}
        <main className="flex-1 overflow-auto">
          {prefersReducedMotion() ? (
            <div className="p-5 flex flex-col gap-5">
              {activeTab === 'projectOverview' && (
                <ProjectOverview onNavigate={handleNavigateWorkshop} />
              )}
              {activeTab === 'workshopOverview' && (
                <WorkshopOverview onNavigateDevice={handleNavigateDevice} />
              )}
              {activeTab === 'deviceOverview' && (
                <DeviceOverview onNavigatePoint={handleNavigatePoint} />
              )}
              {activeTab === 'pointOverview' && (
                <PointOverview />
              )}
              {activeTab === 'analytics' && <AnalyticsTab />}
              {activeTab === 'governance' && <GovernanceTab />}
              {activeTab === 'reports' && <ReportsTab />}
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="p-5 flex flex-col gap-5"
              >
                {activeTab === 'projectOverview' && (
                  <ProjectOverview onNavigate={handleNavigateWorkshop} />
                )}
                {activeTab === 'workshopOverview' && (
                  <WorkshopOverview onNavigateDevice={handleNavigateDevice} />
                )}
                {activeTab === 'deviceOverview' && (
                  <DeviceOverview onNavigatePoint={handleNavigatePoint} />
                )}
                {activeTab === 'pointOverview' && (
                  <PointOverview />
                )}
                {activeTab === 'analytics' && <AnalyticsTab />}
                {activeTab === 'governance' && <GovernanceTab />}
                {activeTab === 'reports' && <ReportsTab />}
              </motion.div>
            </AnimatePresence>
          )}
        </main>
      </div>
    </div>
  );
}

/* ═══════════════ 占位组件 ═══════════════ */
function ReportsTab() {
  return <div className={`text-gray-500 ${B} text-sm`}>报告管理功能将在后续迭代中实现。</div>;
}

/* ═══════════════ 数据分析 ═══════════════ */
import StatCard from '../components/ui/StatCard';
import { RefreshSel } from '../utils/dashboard';

import { useDeviceTree } from '../hooks/useDeviceTree';

function AnalyticsTab() {
  const pid = useAppStore(s => s.currentProjectId);
  const tree = useDeviceTree(pid);
  const [items, setItems] = useState<any>(null);
  const [trend, setTrend] = useState<any>(null);
  const [corr, setCorr] = useState<any>(null);
  const versionRef = useRef(0);
  const ALL_METRICS = ['temperature', 'vibration', 'rpm', 'power', 'humidity', 'pressure'];

  // Get first device from tree
  const devices = tree.map((d: any) => d.device_id).filter(Boolean);
  const firstDevice = devices[0] || '';

  const loadAnomalies = useCallback(async () => {
    const v = ++versionRef.current;
    try {
      const metricsParam = ALL_METRICS.join(',');
      const r = await fetch(`/api/analytics/anomalies/batch?metrics=${metricsParam}&minutes=1440&project_id=${pid}`, { credentials: 'include' });
      if (v !== versionRef.current) return;
      if (!r.ok) { setItems(null); return; }
      const data = await r.json();
      const results = data.results || {};
      const all: any[] = [];
      for (const [metric, result] of Object.entries(results) as [string, any][]) {
        (result.anomalies || []).forEach((a: any) => all.push({ ...a, metric }));
      }
      all.sort((a: any, b: any) => (b.time || '').localeCompare(a.time || ''));
      setItems({ anomalies: all });
    } catch { if (v === versionRef.current) setItems(null); }
  }, [pid]);
  useEffect(() => { loadAnomalies(); const t = setInterval(loadAnomalies, 30000); return () => clearInterval(t); }, [loadAnomalies]);
  useEffect(() => {
    if (!firstDevice) return;
    fetch(`/api/analytics/trend?metric=temperature&device=${firstDevice}&minutes=60&project_id=${pid}`, { credentials: 'include' })
      .then(r => r.json()).then(setTrend).catch(() => {});
  }, [pid, firstDevice]);
  useEffect(() => {
    if (!firstDevice) return;
    fetch(`/api/analytics/correlation?metric_a=temperature&metric_b=vibration&device=${firstDevice}&minutes=60&project_id=${pid}`, { credentials: 'include' })
      .then(r => r.json()).then(setCorr).catch(() => {});
  }, [pid, firstDevice]);
  const list = items?.anomalies || [];
  const loading = items === null;
  const handleClear = async () => {
    if (!window.confirm('确认清除所有异常记录？此操作不可撤销。')) return;
    versionRef.current++;
    try {
      const res = await fetch('/api/analytics/anomaly/acknowledge', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clear_all: true, project_id: pid }),
      });
      if (!res.ok) { loadAnomalies(); return; }
      setItems({ anomalies: [] });
      loadAnomalies();
    } catch { loadAnomalies(); }
  };
  return <>
    <h2 className={`text-lg text-gray-200 ${H}`}>数据分析</h2>
    <div className="grid grid-cols-3 gap-4">
      <StatCard label="异常总数" value={list.length} color="text-red-400" />
      <StatCard label="指标类型" value={new Set(list.map((a: any) => a.metric)).size} color="text-blue-400" />
      <StatCard label="涉及设备" value={new Set(list.map((a: any) => a.machine_id)).size} color="text-orange-400" />
    </div>
    <div className="grid grid-cols-2 gap-4">
      <div className="glass rounded-lg p-4 overflow-visible">
        <div className={`text-xs ${M} uppercase tracking-wider mb-3 ${H}`}>趋势分析</div>
        <div className="text-sm text-gray-400">
          {trend ? `趋势: ${trend.trend} | 斜率: ${trend.slope} | 当前: ${trend.current}` : '加载中...'}
        </div>
      </div>
      <div className="glass rounded-lg p-4 overflow-visible">
        <div className={`text-xs ${M} uppercase tracking-wider mb-3 ${H}`}>关联分析</div>
        <div className={`text-sm ${corr ? K : ''}`} style={{
          color: corr ? corr.correlation > 0.7 ? '#34d399' : corr.correlation > 0.3 ? '#fbbf24' : '#9ca3af' : '#9ca3af'
        }}>
          {corr ? `温度↔振动: ${corr.correlation} (${corr.interpretation})` : '加载中...'}
        </div>
      </div>
    </div>
    <div className="flex items-center justify-between">
      <h3 className={`text-base text-gray-300 ${H}`}>异常检测列表</h3>
      <button onClick={handleClear} disabled={loading}
        className="text-[0.7rem] text-gray-400 hover:text-red-400 transition-colors uppercase tracking-wider font-heading font-semibold disabled:opacity-30 disabled:cursor-not-allowed">
        清空
      </button>
    </div>
    <div className="glass rounded-lg p-4 overflow-visible">
      <div className="max-h-64 overflow-y-auto custom-scroll">
        {loading ? (
          <div className={`text-gray-600 text-sm py-4 text-center ${B}`}>加载中...</div>
        ) : list.length ? (
          list.slice(0, 30).map((a: any, i: number) => (
            <div key={i} className="flex items-center gap-3 py-2 border-b border-gray-800/50 last:border-0 text-sm">
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                a.severity === 'high' ? 'bg-red-500' : a.severity === 'medium' ? 'bg-orange-400' : 'bg-yellow-500'
              }`} />
              <span className="text-[0.65rem] text-gray-400 bg-[#111827] px-1.5 py-0.5 rounded font-body">
                {METRIC_LABELS[a.metric] || a.metric}
              </span>
              <span className={`${M} text-xs ${K}`}>{a.time?.slice(11, 19) || ''}</span>
              <span className={`text-gray-300 truncate flex-1 ${B}`}>{a.machine_id}</span>
              <span className={`text-xs text-gray-500 ${K}`}>Z:{a.z_score}</span>
            </div>
          ))
        ) : (
          <div className={`text-gray-600 text-sm py-4 text-center ${B}`}>无异常</div>
        )}
      </div>
    </div>
  </>;
}

/* ═══════════════ 数据治理 ═══════════════ */
import echarts from '../echarts-setup';
import { Tbl } from '../utils/dashboard';

function GovernanceTab() {
  const pid = useAppStore(s => s.currentProjectId);
  const [d, setD] = useState<any>(null);
  const [interval, setIntervalMs] = useState(1000);
  const trRef = useRef<HTMLDivElement>(null);
  const rdRef = useRef<HTMLDivElement>(null);
  const ti = useRef<echarts.ECharts | null>(null);
  const ri = useRef<echarts.ECharts | null>(null);
  const firstTrend = useRef(true);
  const firstRadar = useRef(true);
  const load = useCallback(async () => {
    try {
      const r = await fetch(`/api/data-governance/overview?project_id=${pid}`, { credentials: 'include' });
      if (r.ok) setD(await r.json());
    } catch (e) { console.error('GovernanceTab load failed:', e); }
  }, [pid]);
  useEffect(() => { load(); const t = setInterval(load, interval); return () => clearInterval(t); }, [load, interval]);

  useEffect(() => {
    if (!d?.quality_trend || !trRef.current) return;
    try {
      if (!ti.current) ti.current = echarts.init(trRef.current, 'dark');
      const isFirst = firstTrend.current;
      ti.current.setOption({
        animation: isFirst, tooltip: { trigger: 'axis' },
        legend: { data: ['完整性', '一致性', '时效性', '准确性'], bottom: 0, textStyle: { color: '#94a3b8', fontSize: 10, fontFamily: 'Inter' } },
        grid: { top: 15, right: 20, bottom: 30, left: 45 },
        xAxis: { type: 'category', data: d.quality_trend.map((x: any) => x.date?.slice(5) || ''), axisLabel: { color: '#64748b', fontSize: 10 } },
        yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: '#64748b', fontSize: 10 }, name: '%', nameTextStyle: { color: '#64748b', fontSize: 10 } },
        series: [
          { name: '完整性', type: 'line', smooth: true, symbol: 'none', data: d.quality_trend.map((x: any) => x.completeness || 0) },
          { name: '一致性', type: 'line', smooth: true, symbol: 'none', data: d.quality_trend.map((x: any) => x.consistency || 0) },
          { name: '时效性', type: 'line', smooth: true, symbol: 'none', data: d.quality_trend.map((x: any) => x.timeliness || 0) },
          { name: '准确性', type: 'line', smooth: true, symbol: 'none', data: d.quality_trend.map((x: any) => x.accuracy || 0) },
        ]
      }, true);
      firstTrend.current = false;
    } catch (e) { console.error(e); }
  }, [d]);
  useEffect(() => {
    if (!d?.dimensions || !rdRef.current) return;
    try {
      if (!ri.current) ri.current = echarts.init(rdRef.current, 'dark');
      const x = d.dimensions;
      const isFirst = firstRadar.current;
      ri.current.setOption({
        animation: isFirst,
        radar: { center: ['50%', '55%'], radius: '65%', indicator: [
          { name: '完整性', max: 100 }, { name: '一致性', max: 100 },
          { name: '时效性', max: 100 }, { name: '准确性', max: 100 }
        ], axisName: { color: '#94a3b8', fontSize: 10, fontFamily: 'Inter' } },
        series: [{ type: 'radar', data: [{ value: [x.completeness, x.consistency, x.timeliness, x.accuracy ?? 85], name: '当前', areaStyle: { color: 'rgba(59,130,246,0.15)' } }] }]
      }, isFirst);
      firstRadar.current = false;
    } catch (e) { console.error(e); }
  }, [d]);
  useEffect(() => {
    const rs = () => { try { ti.current?.resize(); ri.current?.resize(); } catch {} };
    window.addEventListener('resize', rs);
    return () => window.removeEventListener('resize', rs);
  }, []);
  useEffect(() => { return () => { try { ti.current?.dispose(); ri.current?.dispose(); } catch {} }; }, []);

  return <>
    <div className="flex items-center justify-between">
      <h2 className={`text-lg text-gray-200 ${H}`}>数据治理</h2>
      <RefreshSel value={interval} onChange={setIntervalMs} />
    </div>
    <div className="grid grid-cols-4 gap-4">
      <StatCard label="质量评分" value={d?.quality_score ?? 0} color="text-blue-400" decimals={0} unit="分" />
      <StatCard label="完整性" value={d?.dimensions?.completeness ?? 0} color="text-green-400" decimals={0} unit="%" />
      <StatCard label="一致性" value={d?.dimensions?.consistency ?? 0} color="text-orange-400" decimals={0} unit="%" />
      <StatCard label="时效性" value={d?.dimensions?.timeliness ?? 0} color="text-green-400" decimals={0} unit="%" />
    </div>
    <div className="grid grid-cols-2 gap-4">
      <div className="glass rounded-lg p-4 overflow-visible">
        <div className={`text-xs ${M} uppercase tracking-wider mb-2 ${H}`}>质量趋势（7天）</div>
        <div ref={trRef} style={{ width: '100%', minHeight: 260 }} />
      </div>
      <div className="glass rounded-lg p-4 overflow-visible">
        <div className={`text-xs ${M} uppercase tracking-wider mb-2 ${H}`}>维度雷达</div>
        <div ref={rdRef} style={{ width: '100%', minHeight: 260 }} />
      </div>
    </div>
    <div className="grid grid-cols-4 gap-4">
      <StatCard label="今日采集点" value={(d?.collection_stats?.total_points_today ?? 0) / 1000} color="text-blue-400" decimals={1} unit="k" />
      <StatCard label="采集成功率" value={d?.collection_stats?.success_rate ?? 0} color="text-green-400" decimals={0} unit="%" />
      <StatCard label="平均延迟" value={d?.collection_stats?.avg_latency_ms ?? 0} color="text-orange-400" decimals={0} unit="ms" />
      <StatCard label="在线/配置" value={d?.collection_stats?.active_devices ?? 0} color="text-blue-400" decimals={0} />
    </div>
    <div className="grid grid-cols-2 gap-4">
      <div className="glass rounded-lg p-4 overflow-visible">
        <div className={`text-xs ${M} uppercase tracking-wider mb-3 ${H}`}>车间数据质量</div>
        <Tbl
          h={['车间', '省份', '24h数据', '异常率', '评分']}
          rows={(d?.workshops || []).map((w: any) => ({
            cells: [w.name, w.province, ((w.data_points_24h || 0) / 1000).toFixed(1) + 'k', w.anomaly_rate + '%', w.quality_score],
            highlight: w.quality_score > 90 ? '#34d399' : '#fb923c'
          }))}
        />
      </div>
      <div className="glass rounded-lg p-4 overflow-visible">
        <div className={`text-xs ${M} uppercase tracking-wider mb-3 ${H}`}>异常分布</div>
        <Tbl
          h={['车间', '异常', '危险', '警告', '温度', '振动', '功率', '湿度']}
          rows={(d?.anomaly_distribution || []).map((a: any) => ({
            cells: [a.workshop_name, a.total_anomalies ?? a.total, a.critical, a.warning, (a.by_metric || a).temperature ?? 0, (a.by_metric || a).vibration ?? 0, (a.by_metric || a).power ?? 0, (a.by_metric || a).humidity ?? 0]
          }))}
        />
      </div>
    </div>
    <div className="grid grid-cols-2 gap-4">
      <div className="glass rounded-lg p-4 overflow-visible">
        <div className={`text-xs ${M} uppercase tracking-wider mb-3 ${H}`}>规则执行日志</div>
        <Tbl
          h={['规则', '时间', '检查', '通过', '失败', '通过率']}
          rows={(d?.rule_execution_log || []).map((l: any) => ({
            cells: [l.rule, l.time?.slice(11, 19), l.checked, l.passed, l.failed, l.pass_rate + '%']
          }))}
        />
      </div>
      <div className="glass rounded-lg p-4 overflow-visible">
        <div className={`text-xs ${M} uppercase tracking-wider mb-3 ${H}`}>数据字典</div>
        <Tbl
          h={['字段', '标签', '类型', '单位']}
          rows={(d?.data_dictionary || []).map((dd: any) => ({
            cells: [dd.field, dd.label, dd.data_type, dd.unit]
          }))}
        />
      </div>
    </div>
  </>;
}
