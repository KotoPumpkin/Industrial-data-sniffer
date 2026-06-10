import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '../../store/useProjectStore';
import { useNavigationStore } from '../../store/navigationStore';
import { useDeviceTree } from '../../hooks/useDeviceTree';
import { H, B, K, M, Dropdown, TimeRangeSel, TIME_RANGE_OPTS, useChart, METRIC_UNITS, WORKSHOP_NAMES, deviceStatus, POLL_INTERVAL, DATA_FETCH_MINUTES, getTrendDataZoom, updateChartSeries } from '../../utils/dashboard';
import StatCard from '../../components/ui/StatCard';

// Dynamic metrics based on device types present
const CNC_METRICS = [
  { value: 'temperature', label: '温度' }, { value: 'vibration', label: '振动' },
  { value: 'rpm', label: '转速' }, { value: 'power', label: '功率' },
  { value: 'feed_rate', label: '进给速率' }, { value: 'voltage', label: '电压' },
  { value: 'current', label: '电流' },
];
const SENSOR_METRICS = [
  { value: 'temperature', label: '温度' }, { value: 'humidity', label: '湿度' },
  { value: 'pressure', label: '气压' }, { value: 'flow_rate', label: '流量' },
];
const PLC_METRICS = [
  { value: 'count', label: '产量' }, { value: 'defect_count', label: '不良品' },
  { value: 'quality_rate', label: '良品率' }, { value: 'oee', label: 'OEE' },
  { value: 'cycle_time', label: '节拍' },
];

interface Props {
  onNavigateDevice: (deviceId: string) => void;
}

export default function WorkshopOverview({ onNavigateDevice }: Props) {
  const pid = useAppStore(s => s.currentProjectId);
  const wid = useAppStore(s => s.currentWorkshopId);
  const tree = useDeviceTree(pid);
  const [metric, setMetric] = useState('temperature');
  const [timeRange, setTimeRange] = useState(DATA_FETCH_MINUTES);
  const timeRangeRef = useRef(timeRange);
  timeRangeRef.current = timeRange;
  const [trend, setTrend] = useState<any[]>([]);
  const trendRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const trendChart = useChart(trendRef);
  const barChart = useChart(barRef);
  const firstTrend = useRef(true);
  const firstBar = useRef(true);

  const wsName = WORKSHOP_NAMES[wid || ''] || wid || '';

  // ── Filter to current workshop ──
  const devs = tree.filter(d => d.workshop === wid);
  const flatDevs = devs.map(d => {
    const vals: any = {};
    (d.points || []).forEach((p: any) => { if (p.value != null) vals[p.metric] = Number(p.value); });
    return { device_id: d.device_id, device_type: d.device_type, device_type_cn: d.device_type_cn, points: d.points, ...vals };
  });

  // ── Dynamic metric options ──
  const devTypes = [...new Set(flatDevs.map(d => d.device_type))];
  const metricOpts = (() => {
    const seen = new Set<string>();
    const opts: { value: string; label: string }[] = [];
    const add = (src: typeof CNC_METRICS) => src.forEach(o => { if (!seen.has(o.value)) { seen.add(o.value); opts.push(o); } });
    if (devTypes.includes('cnc')) add(CNC_METRICS);
    if (devTypes.includes('sensor')) add(SENSOR_METRICS);
    if (devTypes.includes('plc')) add(PLC_METRICS);
    if (opts.length === 0) add(CNC_METRICS);
    return opts;
  })();

  // ── KPI stats ──
  const kpiStats = (() => {
    const cncs = flatDevs.filter(d => d.device_type === 'cnc' || d.device_type === 'plc');
    const oeeVals = cncs.filter(d => d.oee != null).map(d => d.oee);
    const oee = oeeVals.length > 0 ? oeeVals.reduce((a, b) => a + b, 0) / oeeVals.length : 0;
    const temps = flatDevs.filter(d => d.temperature != null).map(d => d.temperature);
    const vibs = flatDevs.filter(d => d.vibration != null).map(d => d.vibration);
    const pwrs = flatDevs.filter(d => d.power != null).map(d => d.power);
    return {
      oee, temp: temps.length > 0 ? temps.reduce((a, b) => a + b, 0) / temps.length : 0,
      vib: vibs.length > 0 ? vibs.reduce((a, b) => a + b, 0) / vibs.length : 0,
      pwr: pwrs.length > 0 ? pwrs.reduce((a, b) => a + b, 0) / pwrs.length : 0,
    };
  })();

  // ── Trend ──
  const loadTrend = useCallback(async (m: string, animate: boolean, rangeMinutes: number = DATA_FETCH_MINUTES) => {
    if (flatDevs.length === 0) return;
    try {
      const results: { did: string; name: string; data: { time: string; value: number }[] }[] = [];
      // Pick up to 4 devices that have this metric
      const candidates = flatDevs.filter(d => (d.points || []).some((p: any) => p.metric === m)).slice(0, 4);
      for (const dev of candidates) {
        const r = await fetch(`/api/metrics/history?metric=${m}&device=${dev.device_id}&minutes=${rangeMinutes}`, { credentials: 'include' });
        if (!r.ok) continue;
        const rows = await r.json();
        if (!Array.isArray(rows)) continue;
        results.push({
          did: dev.device_id, name: dev.device_id,
          data: rows.map((row: any) => ({ time: row._time || '', value: Number(row._value || 0) })),
        });
      }
      setTrend(results);
      if (animate) firstTrend.current = true;
    } catch (e) { console.error('WorkshopOverview loadTrend failed:', e); }
  }, [flatDevs]);

  useEffect(() => { if (flatDevs.length > 0) loadTrend(metric, true); }, [flatDevs.length > 0, metric]);

  // ── Draw trend ──
  useEffect(() => {
    if (!trendChart.current || trend.length === 0) return;
    const colors = ['#3b82f6', '#fb923c', '#34d399', '#f87171'];
    const allTimes = [...new Set(trend.flatMap(s => s.data.map((p: { time: string }) => p.time)))].sort();
    if (allTimes.length === 0) return;

    const xLabels = allTimes.map((t: string) => t.slice(11, 16));
    const seriesData = trend.map((s, i) => {
      const timeMap: Record<string, number> = {};
      s.data.forEach((p: { time: string; value: number }) => { timeMap[p.time] = p.value; });
      return { name: s.name, data: allTimes.map(t => timeMap[t] ?? null), lineStyle: { color: colors[i % colors.length], width: 2 } };
    });

    const isFirst = firstTrend.current;

    if (isFirst) {
      // ── Full option: structural config + dataZoom slider ──
      trendChart.current.setOption({
        animation: true,
        tooltip: { trigger: 'axis', backgroundColor: '#0a0e18', borderColor: '#232830' },
        legend: { data: trend.map(s => s.name), bottom: 0, textStyle: { color: '#94a3b8', fontSize: 9, fontFamily: 'Inter' } },
        grid: { top: 8, right: 10, bottom: 56, left: 42 },
        xAxis: { type: 'category', data: xLabels, axisLabel: { color: '#64748b', fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }, name: METRIC_UNITS[metric] || '', nameTextStyle: { color: '#64748b', fontSize: 10 } },
        dataZoom: getTrendDataZoom(timeRange),
        series: seriesData.map(s => ({ ...s, type: 'line', smooth: true, symbol: 'none', sampling: 'lttb' })),
      }, true); // notMerge: true — full replace on first render / metric change
    } else {
      // ── Data-only update: preserve dataZoom / grid / axes state ──
      updateChartSeries(trendChart.current, seriesData.map(s => ({ ...s, type: 'line', smooth: true, symbol: 'none' })), xLabels);
    }

    firstTrend.current = false;
  }, [trend, trendChart, metric]);

  // ── Draw bar comparison ──
  useEffect(() => {
    if (!barChart.current || flatDevs.length === 0) return;
    const names = flatDevs.map(d => d.device_id);
    const temps = flatDevs.map(d => d.temperature ?? null);
    const vibs = flatDevs.map(d => d.vibration ?? null);
    const pwrs = flatDevs.map(d => d.power ?? null);
    const series = [
      { name: '温度', type: 'bar', data: temps, itemStyle: { color: '#f87171' }, barWidth: '25%' },
      { name: '振动', type: 'bar', data: vibs, itemStyle: { color: '#fb923c' }, barWidth: '25%' },
      { name: '功率', type: 'bar', yAxisIndex: 1, data: pwrs, itemStyle: { color: '#3b82f6' }, barWidth: '25%' },
    ];
    if (firstBar.current) {
      barChart.current.setOption({
        animation: true,
        tooltip: { trigger: 'axis', backgroundColor: '#0a0e18', borderColor: '#232830' },
        legend: { data: ['温度', '振动', '功率'], bottom: 0, textStyle: { color: '#94a3b8', fontSize: 10, fontFamily: 'Inter' } },
        grid: { top: 8, right: 10, bottom: 36, left: 40 },
        xAxis: { type: 'category', data: names, axisLabel: { color: '#94a3b8', fontSize: 10 } },
        yAxis: [
          { type: 'value', name: '°C / mm/s', axisLabel: { color: '#94a3b8', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
          { type: 'value', name: 'W', axisLabel: { color: '#94a3b8', fontSize: 10 }, splitLine: { show: false } },
        ],
        series,
      }, true);
    } else {
      updateChartSeries(barChart.current, series);
    }
    firstBar.current = false;
  }, [flatDevs, barChart]);

  // ── Reset first-render flags on metric or timeRange change ──
  useEffect(() => { firstTrend.current = true; firstBar.current = true; }, [metric, timeRange]);

  // ── Polling ──
  useEffect(() => {
    const t = setInterval(() => { if (flatDevs.length > 0) loadTrend(metric, false, timeRangeRef.current); }, POLL_INTERVAL);
    return () => clearInterval(t);
  }, [loadTrend, metric, flatDevs.length]);

  if (!pid) return null;

  // ── Aggregate view: all workshops under current project ──
  if (!wid) {
    const wsIdsAll = [...new Set(tree.map(d => d.workshop).filter(Boolean))];
    const wsStatsAll = wsIdsAll.map(widKey => {
      const devs = tree.filter(d => d.workshop === widKey);
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
      return { wid: widKey, name: WORKSHOP_NAMES[widKey] || widKey, devCount: devs.length, ok, warn, alarm, oee: oeeCount > 0 ? avgOee / oeeCount : 0 };
    });
    const totalDevs = tree.length;
    const totalPoints = tree.reduce((s, d) => s + (d.points || []).length, 0);
    const projColor = '#3b82f6';
    return (
      <>
        <h1 className={`text-2xl text-white ${H}`}>全部车间概况</h1>
        <p className={`text-sm text-gray-500 mb-5 ${B}`}>
          {wsIdsAll.length} 个车间 · {totalDevs} 台设备 · {totalPoints} 个采集点位
        </p>
        <div className="grid grid-cols-3 gap-3 mb-5">
          <StatCard label="车间数" value={wsIdsAll.length} color="text-blue-400" />
          <StatCard label="设备数" value={totalDevs} color="text-gray-200" />
          <StatCard label="采集点位" value={totalPoints} color="text-gray-200" />
        </div>
        <div className="flex items-center justify-between mb-3">
          <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>车间列表</div>
          <div className={`text-[0.7rem] ${M} ${B}`}>点击进入车间聚焦视图 →</div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {wsStatsAll.map((ws, i) => (
            <motion.div
              key={ws.wid}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
              onClick={() => { useAppStore.getState().setCurrentWorkshop(ws.wid); useNavigationStore.getState().drillTo('workshop'); }}
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

  return (
    <>
      <h1 className={`text-2xl text-white ${H}`}>{wsName}</h1>
      <p className={`text-sm text-gray-500 mb-5 ${B}`}>
        {devs.length} 台设备 · {devs.reduce((s, d) => s + (d.points || []).length, 0)} 个采集点位
      </p>

      {/* KPI Grid (4 columns) */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        <StatCard label="运行效率" value={kpiStats.oee} unit="%" color="text-blue-400" decimals={1} />
        <StatCard label="平均温度" value={kpiStats.temp} unit="°C" color={kpiStats.temp > 65 ? 'text-red-400' : 'text-gray-200'} decimals={1} />
        <StatCard label="平均振动" value={kpiStats.vib} unit="mm/s" color={kpiStats.vib > 3 ? 'text-orange-400' : 'text-gray-200'} decimals={2} />
        <StatCard label="平均功率" value={kpiStats.pwr} unit="W" color="text-gray-200" decimals={0} />
      </div>

      {/* Chart Row */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div className="glass rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>
              运行效率趋势（{TIME_RANGE_OPTS.find(o => o.value === timeRange)?.label || timeRange + '分'}）
            </div>
            <div className="flex items-center gap-2">
              <Dropdown value={metric} opts={metricOpts} onChange={(v) => setMetric(v)} />
              <TimeRangeSel value={timeRange} onChange={(v) => { setTimeRange(v); loadTrend(metric, true, v); }} />
            </div>
          </div>
          <div ref={trendRef} style={{ width: '100%', height: 260 }} />
        </div>
        <div className="glass rounded-lg p-4">
          <div className={`text-xs ${M} uppercase tracking-wider mb-2 ${H}`}>设备综合指标对比</div>
          <div ref={barRef} style={{ width: '100%', height: 260 }} />
        </div>
      </div>

      {/* Device Cards (2 columns) */}
      <div className="flex items-center justify-between mb-3">
        <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>设备列表</div>
        <div className={`text-[0.7rem] ${M} ${B}`}>点击设备进入点位详情 →</div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {flatDevs.map(d => {
          const st = deviceStatus(d);
          const stColor = st === 'alarm' ? '#f87171' : st === 'warn' ? '#fb923c' : '#34d399';
          const mainMetric = d.oee != null ? `OEE ${d.oee.toFixed(1)}%` :
            d.temperature != null ? `${d.temperature.toFixed(1)}°C` :
              d.power != null ? `${d.power.toFixed(0)}W` : '--';
          const mainColor = d.oee != null ? '#3b82f6' : st === 'alarm' ? '#f87171' : '#e8eaef';
          return (
            <div key={d.device_id} onClick={() => onNavigateDevice(d.device_id)}
              className="glass rounded-lg p-4 cursor-pointer hover:bg-[#161a22] hover:border-blue-500/30 transition-all group">
              <div className="flex items-center gap-3">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: stColor }} />
                <div className="flex-1 min-w-0">
                  <div className={`text-sm text-gray-200 ${H}`}>{d.device_id}</div>
                  <div className={`text-[0.7rem] ${M} mt-0.5`}>{d.device_type_cn || d.device_type} · 点位 {(d.points || []).length} 个</div>
                </div>
                <span className={`text-lg ${K}`} style={{ color: mainColor }}>{mainMetric}</span>
                <span className={`text-xs ${M} group-hover:text-blue-400 transition-colors pointer-events-none`}>▶</span>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
