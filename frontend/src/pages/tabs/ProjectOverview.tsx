import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '../../store/useProjectStore';
import { useDeviceTree } from '../../hooks/useDeviceTree';
import { H, B, K, M, Dropdown, TimeRangeSel, TIME_RANGE_OPTS, useChart, METRIC_LABELS, METRIC_UNITS, PROJECT_NAMES, PROJECT_COLORS, PROJECT_REGIONS, WORKSHOP_NAMES, deviceStatus, POLL_INTERVAL, DATA_FETCH_MINUTES, getTrendDataZoom, updateChartSeries } from '../../utils/dashboard';
import StatCard from '../../components/ui/StatCard';

const METRIC_OPTS = [
  { value: 'temperature', label: '温度' }, { value: 'vibration', label: '振动' },
  { value: 'power', label: '功率' }, { value: 'rpm', label: '转速' },
  { value: 'humidity', label: '湿度' }, { value: 'oee', label: 'OEE' },
];

interface Props { onNavigate: (workshopId: string) => void }

export default function ProjectOverview({ onNavigate }: Props) {
  const pid = useAppStore(s => s.currentProjectId);
  const tree = useDeviceTree(pid);
  const [kpi, setKpi] = useState<any>(null);
  const [metric, setMetric] = useState('temperature');
  const [timeRange, setTimeRange] = useState(DATA_FETCH_MINUTES);
  const [wsTrend, setWsTrend] = useState<any[]>([]);
  const trendRef = useRef<HTMLDivElement>(null);
  const pieRef = useRef<HTMLDivElement>(null);
  const trendChart = useChart(trendRef);
  const pieChart = useChart(pieRef);
  const firstTrend = useRef(true);
  const firstPie = useRef(true);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  const projName = PROJECT_NAMES[pid || ''] || pid || '';
  const projColor = PROJECT_COLORS[pid || ''] || '#3b82f6';

  // ── KPI ──
  useEffect(() => {
    if (!pid) return;
    fetch(`/api/projects/overview`, { credentials: 'include' })
      .then(r => r.json()).then((d: any) => {
        const item = (d || []).find((x: any) => x.id === pid);
        if (item) setKpi(item);
      }).catch(() => {});
  }, [pid]);

  // ── Workshop grouping ──
  const wsIds = [...new Set(tree.map(d => d.workshop).filter(Boolean))];
  const wsStats = wsIds.map(wid => {
    const devs = tree.filter(d => d.workshop === wid);
    const flat = devs.map(d => {
      const vals: any = {};
      (d.points || []).forEach((p: any) => { if (p.value != null) vals[p.metric] = Number(p.value); });
      return { name: d.device_id, ...vals };
    });
    const ok = flat.filter(d => deviceStatus(d) === 'ok').length;
    const warn = flat.filter(d => deviceStatus(d) === 'warn').length;
    const alarm = flat.filter(d => deviceStatus(d) === 'alarm').length;
    const avgOee = flat.filter(d => d.oee != null).reduce((s, d) => s + d.oee, 0);
    const oeeCount = flat.filter(d => d.oee != null).length;
    return { wid, name: WORKSHOP_NAMES[wid] || wid, devCount: devs.length, ok, warn, alarm, oee: oeeCount > 0 ? avgOee / oeeCount : 0 };
  });

  // ── Status pie ──
  useEffect(() => {
    if (!pieChart.current || tree.length === 0) return;
    const flat = tree.map(d => {
      const vals: any = {};
      (d.points || []).forEach((p: any) => { if (p.value != null) vals[p.metric] = Number(p.value); });
      return { name: d.device_id, ...vals };
    });
    const alarms = flat.filter(d => deviceStatus(d) === 'alarm').length;
    const warns = flat.filter(d => deviceStatus(d) === 'warn').length;
    const online = flat.length - alarms - warns;
    const pieData = [
      { value: online, name: '在线', itemStyle: { color: '#34d399' } },
      { value: alarms, name: '告警', itemStyle: { color: '#f87171' } },
      { value: warns, name: '异常', itemStyle: { color: '#fb923c' } },
    ];
    if (firstPie.current) {
      pieChart.current.setOption({
        backgroundColor: '#0a0e18',
        animation: true,
        tooltip: { trigger: 'item', backgroundColor: '#0a0e18', borderColor: '#232830' },
        legend: { orient: 'vertical', right: 8, top: 'center', itemGap: 10, textStyle: { color: '#94a3b8', fontSize: 10, fontFamily: 'Inter' } },
        series: [{
          type: 'pie', radius: ['50%', '75%'], center: ['40%', '50%'],
          avoidLabelOverlap: false,
          label: { show: true, position: 'outside', formatter: '' },
          labelLine: { show: false },
          emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold', formatter: '{b}\n{c}', color: '#e2e8f0' } },
        }],
      }, true);
    } else {
      pieChart.current.setOption({ animationDurationUpdate: 0, series: [{ data: pieData, emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold', formatter: '{b}\n{c}', color: '#e2e8f0' } } }] }, false);
    }
    firstPie.current = false;
  }, [tree, pieChart]);

  // ── Workshop trend (one line per workshop) — batch endpoint ──
  const loadWsTrend = useCallback(async (m: string, animate: boolean, rangeMinutes: number = DATA_FETCH_MINUTES) => {
    if (!pid || wsIds.length === 0) return;
    try {
      // Pick representative device per workshop
      const reps: string[] = [];
      for (const wid of wsIds) {
        const devs = tree.filter(d => d.workshop === wid && (d.points || []).some((p: any) => p.metric === m));
        const rep = devs[0] || tree.find(d => d.workshop === wid);
        if (rep) reps.push(rep.device_id);
      }
      if (reps.length === 0) return;
      const r = await fetch(`/api/metrics/history/batch?metric=${m}&devices=${reps.join(',')}&minutes=${rangeMinutes}`, { credentials: 'include' });
      if (!r.ok) return;
      const data = await r.json();
      const series = data.series || {};
      const results: { wid: string; name: string; data: { time: string; value: number }[] }[] = [];
      for (const wid of wsIds) {
        const devs = tree.filter(d => d.workshop === wid && (d.points || []).some((p: any) => p.metric === m));
        const rep = devs[0] || tree.find(d => d.workshop === wid);
        if (!rep) continue;
        const rows = series[rep.device_id] || [];
        if (!Array.isArray(rows)) continue;
        results.push({
          wid,
          name: WORKSHOP_NAMES[wid] || wid,
          data: rows.map((row: any) => ({ time: row._time || '', value: Number(row._value || 0) })),
        });
      }
      setWsTrend(results);
      if (animate) firstTrend.current = true;
    } catch (e) { console.error('ProjectOverview loadWsTrend failed:', e); }
  }, [pid, wsIds, tree]);

  useEffect(() => { if (tree.length > 0) loadWsTrend(metric, true); }, [tree.length > 0, metric]);

  // ── Draw trend chart ──
  useEffect(() => {
    if (!trendChart.current || wsTrend.length === 0) return;
    const colors = ['#3b82f6', '#fb923c', '#34d399', '#f87171', '#22d3ee', '#a78bfa'];
    const allTimes = [...new Set(wsTrend.flatMap(s => s.data.map((p: { time: string }) => p.time)))].sort();
    if (allTimes.length === 0) return;

    const xLabels = allTimes.map((t: string) => t.slice(11, 16));
    const seriesData = wsTrend.map((s, i) => {
      const timeMap: Record<string, number> = {};
      s.data.forEach((p: { time: string; value: number }) => { timeMap[p.time] = p.value; });
      return {
        name: s.name,
        data: allTimes.map(t => timeMap[t] ?? null),
        lineStyle: { color: colors[i % colors.length], width: 2 },
      };
    });

    const isFirst = firstTrend.current;

    if (isFirst) {
      // ── Full option: structural config + dataZoom slider ──
      trendChart.current.setOption({
        animation: true,
        tooltip: { trigger: 'axis', backgroundColor: '#0a0e18', borderColor: '#232830' },
        legend: { data: wsTrend.map(s => s.name), bottom: 0, textStyle: { color: '#94a3b8', fontSize: 9, fontFamily: 'Inter' } },
        grid: { top: 8, right: 10, bottom: 56, left: 42 },
        xAxis: {
          type: 'category', data: xLabels,
          axisLabel: { color: '#64748b', fontSize: 10 },
        },
        yAxis: {
          type: 'value', axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
          name: METRIC_UNITS[metric] || '', nameTextStyle: { color: '#64748b', fontSize: 10 },
        },
        dataZoom: getTrendDataZoom(timeRange),
        series: seriesData.map(s => ({ ...s, type: 'line', smooth: true, symbol: 'none', sampling: 'lttb' })),
      }, true); // notMerge: true — full replace on first render / metric change
    } else {
      // ── Data-only update: preserve dataZoom / grid / axes state ──
      updateChartSeries(trendChart.current, seriesData.map(s => ({ ...s, type: 'line', smooth: true, symbol: 'none' })), xLabels);
    }

    firstTrend.current = false;
  }, [wsTrend, trendChart, metric]);

  // ── Reset first-render flags on metric change ──
  useEffect(() => { firstTrend.current = true; firstPie.current = true; }, [metric]);

  // ── Polling refresh (no animation) ──
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      if (wsIds.length > 0) loadWsTrend(metric, false, DATA_FETCH_MINUTES);
    }, POLL_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [loadWsTrend, metric]);

  if (!pid) return null;

  const pointCount = tree.reduce((s, d) => s + (d.points || []).length, 0);

  return (
    <>
      <h1 className={`text-2xl text-white ${H}`}>{projName}</h1>
      <p className={`text-sm text-gray-500 mb-5 ${B}`}>
        {PROJECT_REGIONS[pid] ? `覆盖 ${PROJECT_REGIONS[pid]}，` : ''}{wsIds.length} 个车间 · {tree.length} 台设备 · {pointCount} 个采集点位
      </p>

      {/* KPI Grid (3×2) */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <StatCard label="车间数" value={kpi?.workshop_count ?? wsIds.length} color="text-blue-400" />
        <StatCard label="设备数" value={kpi?.device_count ?? tree.length} color="text-gray-200" />
        <StatCard label="采集点位" value={kpi?.point_count ?? pointCount} color="text-gray-200" />
        <StatCard label="运行效率" value={kpi?.oee_avg ?? 0} unit="%" color="text-blue-400" decimals={1} />
        <StatCard label="产量(24h)" value={(kpi?.production_count ?? 0) / 1000} unit="k" color="text-gray-200" decimals={1} />
        <StatCard label="良品率" value={kpi?.quality_rate ?? 0} unit="%" color="text-green-400" decimals={1} />
      </div>

      {/* Trend Chart (full width) + Pie (side by side) */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div className="glass rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>
              车间 {METRIC_LABELS[metric] || metric} 对比（{TIME_RANGE_OPTS.find(o => o.value === timeRange)?.label || timeRange + '分'}）
            </div>
            <div className="flex items-center gap-2">
              <Dropdown value={metric} opts={METRIC_OPTS} onChange={(v) => setMetric(v)} />
              <TimeRangeSel value={timeRange} onChange={(v) => { setTimeRange(v); loadWsTrend(metric, true, v); }} />
            </div>
          </div>
          <div ref={trendRef} style={{ width: '100%', height: 260 }} />
        </div>
        <div className="glass rounded-lg p-4">
          <div className={`text-xs ${M} uppercase tracking-wider mb-2 ${H}`}>设备状态分布</div>
          <div ref={pieRef} style={{ width: '100%', height: 260 }} />
        </div>
      </div>

      {/* Workshop Cards (3 columns) */}
      <div className="flex items-center justify-between mb-3">
        <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>车间列表</div>
        <div className={`text-[0.7rem] ${M} ${B}`}>点击进入车间概览 →</div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {wsStats.map((ws, i) => (
          <motion.div
            key={ws.wid}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
            onClick={() => onNavigate(ws.wid)}
            className="glass glass-interactive rounded-lg p-4 cursor-pointer group"
          >
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: projColor }} />
              <div className="flex-1 min-w-0">
                <div className={`text-sm text-gray-200 ${H}`}>{ws.name}</div>
                <div className={`text-[0.7rem] ${M} mt-0.5`}>
                  设备 {ws.devCount} 台
                  {ws.alarm > 0 && <span className="text-red-400 ml-1">· 告警 {ws.alarm}</span>}
                  {ws.warn > 0 && <span className="text-orange-400 ml-1">· 异常 {ws.warn}</span>}
                </div>
              </div>
              <span className={`text-lg ${K} tabular-nums`} style={{ color: projColor }}>
                {ws.oee > 0 ? ws.oee.toFixed(1) + '%' : '--'}
              </span>
              <span className="text-xs text-gray-500 group-hover:text-blue-400 transition-colors duration-200 pointer-events-none">▶</span>
            </div>
          </motion.div>
        ))}
      </div>
    </>
  );
}
