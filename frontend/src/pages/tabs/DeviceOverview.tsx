import { useState, useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '../../store/useProjectStore';
import { useNavigationStore } from '../../store/navigationStore';
import { useDeviceTree } from '../../hooks/useDeviceTree';
import { H, B, K, M, Dropdown, TimeRangeSel, TIME_RANGE_OPTS, useChart, METRIC_LABELS, METRIC_UNITS, WORKSHOP_NAMES, deviceStatus, POLL_INTERVAL, DATA_FETCH_MINUTES, getTrendDataZoom, updateChartSeries } from '../../utils/dashboard';
import StatCard from '../../components/ui/StatCard';
import echarts from '../../echarts-setup';

interface Props {
  onNavigatePoint: (metric: string) => void;
}

const POINT_COLORS: Record<string, string> = {
  temperature: '#f87171', vibration: '#fb923c', rpm: '#3b82f6', power: '#34d399',
  feed_rate: '#a78bfa', voltage: '#fbbf24', current: '#22d3ee',
  humidity: '#3b82f6', pressure: '#a78bfa', flow_rate: '#22d3ee',
  count: '#3b82f6', defect_count: '#f87171', quality_rate: '#34d399', oee: '#3b82f6', cycle_time: '#fb923c',
};

export default function DeviceOverview({ onNavigatePoint }: Props) {
  const pid = useAppStore(s => s.currentProjectId);
  const did = useAppStore(s => s.currentDeviceId);
  const tree = useDeviceTree(pid);
  const [report, setReport] = useState<any>(null);
  const [combined, setCombined] = useState<any>(null);
  const [selPoint, setSelPoint] = useState('temperature');
  const [timeRange, setTimeRange] = useState(DATA_FETCH_MINUTES);
  const timeRangeRef = useRef(timeRange);
  timeRangeRef.current = timeRange;

  const trendRef = useRef<HTMLDivElement>(null);
  const distRef = useRef<HTMLDivElement>(null);
  const scatterRef = useRef<HTMLDivElement>(null);
  const radarRef = useRef<HTMLDivElement>(null);
  const trendChart = useChart(trendRef);
  const distChart = useChart(distRef);
  const scatterChart = useChart(scatterRef);
  const radarChart = useChart(radarRef);
  const firstTrend = useRef(true);
  const firstDist = useRef(true);
  const firstScatter = useRef(true);
  const firstRadar = useRef(true);

  // ── Find device info and points ──
  const devInfo = tree.find(d => d.device_id === did);
  const points = devInfo?.points || [];
  const devType = devInfo?.device_type || '';
  const devTypeCn = devInfo?.device_type_cn || devType;

  // Build point dropdown options — deduplicate by metric, show count when multiple points share same metric
  const pointOpts = (() => {
    const byMetric: Record<string, { unit: string; count: number }> = {};
    points.forEach((p: any) => {
      if (!byMetric[p.metric]) byMetric[p.metric] = { unit: p.unit || '', count: 0 };
      byMetric[p.metric].count++;
    });
    return Object.entries(byMetric).map(([metric, info]) => ({
      value: metric,
      label: info.count > 1
        ? `${METRIC_LABELS[metric] || metric} · ${info.count}个测点 (${info.unit})`
        : `${METRIC_LABELS[metric] || metric} (${info.unit})`,
    }));
  })();

  // ── Full device data (report + combined trend merged) ──
  const loadFull = useCallback(async (rangeMinutes: number = DATA_FETCH_MINUTES) => {
    if (!did) return;
    try {
      const r = await fetch(`/api/analytics/device_report/${did}/full?minutes=${rangeMinutes}`, { credentials: 'include' });
      if (r.ok) {
        const data = await r.json();
        setReport(data.report || null);
        setCombined(data.combined_trend || null);
      }
    } catch (e) { console.error('DeviceOverview loadFull failed:', e); }
  }, [did]);
  useEffect(() => { loadFull(); }, [loadFull]);

  // ── Selected point stats ──
  const ptStats = report?.metrics?.[selPoint];
  const latest = ptStats?.latest ?? 0;
  const mean = ptStats?.mean ?? 0;
  const max = ptStats?.max ?? 0;
  const min = ptStats?.min ?? 0;
  const ptUnit = METRIC_UNITS[selPoint] || '';
  const ptColor = POINT_COLORS[selPoint] || '#3b82f6';

  // ── Trend chart ──
  useEffect(() => {
    if (!trendChart.current || !combined) return;
    const idx = combined.metrics?.indexOf(selPoint);
    if (idx === undefined || idx < 0) return;
    const times = combined.times || [];
    // Use index-based mapping: xAxis categories define positions, series data = values only
    // This avoids category-name matching issues with dataZoom and ensures correct rendering
    const vals: (number | null)[] = combined.series?.[selPoint] || [];

    const isFirst = firstTrend.current;

    if (isFirst) {
      // ── Full option: structural config + dataZoom slider ──
      trendChart.current.setOption({
        animation: true,
        tooltip: { trigger: 'axis', backgroundColor: '#0a0e18', borderColor: '#232830' },
        grid: { top: 8, right: 12, bottom: 44, left: 48 },
        xAxis: { type: 'category', data: times, axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { show: false } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }, name: ptUnit, nameTextStyle: { color: '#64748b', fontSize: 10 } },
        dataZoom: getTrendDataZoom(timeRange),
        series: [{
          type: 'line', data: vals,
          smooth: true, symbol: 'none', connectNulls: false,
          lineStyle: { color: ptColor, width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: ptColor + '30' }, { offset: 1, color: ptColor + '04' },
            ]),
          },
          markLine: {
            silent: true, symbol: 'none',
            data: [{ yAxis: mean, name: '均值', label: { color: '#94a3b8', fontSize: 10 }, lineStyle: { color: 'rgba(255,255,255,0.3)', type: 'dashed' } }],
          },
        }],
      }, true); // notMerge: true — full replace on first render / metric change
    } else {
      // ── Data-only update: preserve dataZoom / grid / axes state ──
      updateChartSeries(trendChart.current, [{
        data: vals,
        markLine: {
          silent: true, symbol: 'none',
          data: [{ yAxis: mean, name: '均值', label: { color: '#94a3b8', fontSize: 10 }, lineStyle: { color: 'rgba(255,255,255,0.3)', type: 'dashed' } }],
        },
      }], times);
    }

    firstTrend.current = false;
  }, [combined, selPoint, trendChart]);

  // ── Distribution histogram ──
  useEffect(() => {
    if (!distChart.current || !combined) return;
    const vals = (combined.series?.[selPoint] || []).filter((v: any) => v != null) as number[];
    if (vals.length < 2) return;
    const sorted = [...vals].sort((a, b) => a - b);
    const bins = 20;
    const bw = (sorted[sorted.length - 1] - sorted[0]) / bins;
    if (bw <= 0) return;
    const hist = Array(bins).fill(0);
    sorted.forEach(v => { const i = Math.min(bins - 1, Math.floor((v - sorted[0]) / bw)); hist[i]++; });
    const labels = hist.map((_, i) => (sorted[0] + i * bw).toFixed(1));
    const distSeries = [{ type: 'bar', data: hist, itemStyle: { color: ptColor + '80', borderRadius: 2 }, barWidth: '90%' }];
    if (firstDist.current) {
      distChart.current.setOption({
        animation: true,
        tooltip: { trigger: 'axis', backgroundColor: '#0a0e18', borderColor: '#232830' },
        grid: { top: 8, right: 10, bottom: 24, left: 36 },
        xAxis: { data: labels, axisLabel: { color: '#94a3b8', fontSize: 9 }, splitLine: { show: false } },
        yAxis: { axisLabel: { color: '#94a3b8', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
        series: distSeries,
      }, true);
    } else {
      updateChartSeries(distChart.current, distSeries, labels);
    }
    firstDist.current = false;
  }, [combined, selPoint, distChart]);

  // ── Scatter: selected vs next point ──
  useEffect(() => {
    if (!scatterChart.current || !combined) return;
    const metrics = combined.metrics || [];
    const idx = metrics.indexOf(selPoint);
    if (idx < 0 || metrics.length < 2) return;
    const nextIdx = (idx + 1) % metrics.length;
    const nextMetric = metrics[nextIdx];
    const xVals = combined.series?.[selPoint] || [];
    const yVals = combined.series?.[nextMetric] || [];
    const data: number[][] = [];
    for (let i = 0; i < Math.min(xVals.length, yVals.length); i += 3) {
      if (xVals[i] != null && yVals[i] != null) data.push([xVals[i], yVals[i]]);
    }
    const scatterSeries = [{ type: 'scatter', data, symbolSize: 3, itemStyle: { color: ptColor + '80' } }];
    if (firstScatter.current) {
      scatterChart.current.setOption({
        animation: true,
        tooltip: { backgroundColor: '#0a0e18', borderColor: '#232830' },
        grid: { top: 8, right: 10, bottom: 24, left: 48 },
        xAxis: { name: METRIC_LABELS[selPoint] || selPoint, type: 'value', nameTextStyle: { color: '#94a3b8', fontSize: 10 }, axisLabel: { color: '#94a3b8', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
        yAxis: { name: METRIC_LABELS[nextMetric] || nextMetric, type: 'value', nameTextStyle: { color: '#94a3b8', fontSize: 10 }, axisLabel: { color: '#94a3b8', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
        series: scatterSeries,
      }, true);
    } else {
      updateChartSeries(scatterChart.current, scatterSeries);
    }
    firstScatter.current = false;
  }, [combined, selPoint, scatterChart]);

  // ── Radar ──
  useEffect(() => {
    if (!radarChart.current || !report?.metrics) return;
    const metrics = Object.keys(report.metrics);
    if (metrics.length === 0) return;
    const indicators = metrics.map(m => ({
      name: METRIC_LABELS[m] || m,
      max: (report.metrics[m].max || 0) * 1.3 || 100,
    }));
    const curVals = metrics.map(m => report.metrics[m].latest);
    const baseVals = metrics.map(m => report.metrics[m].mean);
    const radarSeries = [
      {
        type: 'radar', data: [{ value: curVals, name: '当前值', areaStyle: { color: '#3b82f620' }, lineStyle: { color: '#3b82f6' }, symbol: 'circle', symbolSize: 4 }],
      },
      {
        type: 'radar', data: [{ value: baseVals, name: '均值', areaStyle: { color: 'transparent' }, lineStyle: { color: '#94a3b8', type: 'dashed' }, symbol: 'none' }],
      },
    ];
    if (firstRadar.current) {
      radarChart.current.setOption({
        animation: true,
        legend: { data: ['当前值', '均值'], bottom: 0, textStyle: { color: '#94a3b8', fontSize: 10, fontFamily: 'Inter' } },
        radar: {
          center: ['50%', '50%'], radius: '60%',
          indicator: indicators,
          axisName: { color: '#94a3b8', fontSize: 10 },
          splitArea: { areaStyle: { color: ['rgba(255,255,255,0.02)', 'transparent', 'rgba(255,255,255,0.02)', 'transparent'] } },
        },
        series: radarSeries,
      }, true);
    } else {
      radarChart.current.setOption({ animationDurationUpdate: 0, radar: { indicator: indicators }, series: radarSeries }, false);
    }
    firstRadar.current = false;
  }, [report, radarChart]);

  // ── Reset first-render flags on metric or timeRange change ──
  useEffect(() => {
    firstTrend.current = true;
    firstDist.current = true;
    firstScatter.current = true;
    firstRadar.current = true;
  }, [selPoint, timeRange]);

  // ── Polling (respects user-selected timeRange via ref) ──
  useEffect(() => {
    const t = setInterval(() => { loadFull(timeRangeRef.current); }, POLL_INTERVAL);
    return () => clearInterval(t);
  }, [loadFull]);

  // Set initial selected point from device
  useEffect(() => {
    if (points.length > 0 && !points.find((p: any) => p.metric === selPoint)) {
      setSelPoint(points[0].metric);
    }
  }, [points]);

  if (!pid) return null;

  // ── Aggregate view: all devices under current project ──
  if (!did) {
    const wsIdsAll = [...new Set(tree.map(d => d.workshop).filter(Boolean))];
    const totalDevs = tree.length;
    const totalPoints = tree.reduce((s, d) => s + (d.points || []).length, 0);
    const flatAll = tree.map(d => {
      const vals: any = {};
      (d.points || []).forEach((p: any) => { if (p.value != null) vals[p.metric] = Number(p.value); });
      return { device_id: d.device_id, device_type: d.device_type, device_type_cn: d.device_type_cn, workshop: d.workshop, points: d.points, ...vals };
    });
    const alarms = flatAll.filter(d => deviceStatus(d) === 'alarm').length;
    const warns = flatAll.filter(d => deviceStatus(d) === 'warn').length;
    return (
      <>
        <h1 className={`text-2xl text-white ${H}`}>全部设备概况</h1>
        <p className={`text-sm text-gray-500 mb-5 ${B}`}>
          {wsIdsAll.length} 个车间 · {totalDevs} 台设备 · {totalPoints} 个采集点位
        </p>
        <div className="grid grid-cols-4 gap-3 mb-5">
          <StatCard label="设备总数" value={totalDevs} color="text-blue-400" />
          <StatCard label="采集点位" value={totalPoints} color="text-gray-200" />
          <StatCard label="告警设备" value={alarms} color={alarms > 0 ? 'text-red-400' : 'text-green-400'} />
          <StatCard label="异常设备" value={warns} color={warns > 0 ? 'text-orange-400' : 'text-gray-200'} />
        </div>
        {wsIdsAll.map(wsIdKey => {
          const wsDevs = flatAll.filter(d => d.workshop === wsIdKey);
          if (wsDevs.length === 0) return null;
          return (
            <div key={wsIdKey} className="mb-5">
              <div className="flex items-center justify-between mb-3">
                <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>
                  {WORKSHOP_NAMES[wsIdKey] || wsIdKey} · {wsDevs.length} 台设备
                </div>
                <div className={`text-[0.7rem] ${M} ${B}`}>点击设备进入聚焦视图 →</div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {wsDevs.map(d => {
                  const st = deviceStatus(d);
                  const stColor = st === 'alarm' ? '#f87171' : st === 'warn' ? '#fb923c' : '#34d399';
                  const mainMetric = d.oee != null ? `OEE ${d.oee.toFixed(1)}%` :
                    d.temperature != null ? `${d.temperature.toFixed(1)}°C` :
                      d.power != null ? `${d.power.toFixed(0)}W` : '--';
                  const mainColor = d.oee != null ? '#3b82f6' : st === 'alarm' ? '#f87171' : '#e8eaef';
                  return (
                    <div key={d.device_id}
                      onClick={() => { useAppStore.getState().setCurrentDevice(d.device_id); useNavigationStore.getState().drillTo('device'); }}
                      className="glass rounded-lg p-4 cursor-pointer hover:bg-[#161a22] hover:border-blue-500/30 transition-all group">
                      <div className="flex items-center gap-3">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: stColor }} />
                        <div className="flex-1 min-w-0">
                          <div className={`text-sm text-gray-200 ${H}`}>{d.device_id}</div>
                          <div className={`text-[0.7rem] ${M} mt-0.5`}>
                            {d.device_type_cn || d.device_type} · 点位 {(d.points || []).length} 个
                            {st === 'alarm' && <span className="text-red-400 ml-1">· 告警</span>}
                            {st === 'warn' && <span className="text-orange-400 ml-1">· 异常</span>}
                          </div>
                        </div>
                        <span className={`text-lg ${K}`} style={{ color: mainColor }}>{mainMetric}</span>
                        <span className="text-xs text-gray-500 group-hover:text-blue-400 transition-colors pointer-events-none">▶</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </>
    );
  }

  return (
    <>
      {/* Title + Point Selector */}
      <div className="flex items-center gap-4 mb-5">
        <h1 className={`text-2xl text-white ${H}`}>{did}</h1>
        <span className="flex items-center gap-1.5 text-sm text-gray-400">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#3b82f6' }} />
          {devTypeCn}
        </span>
        <span className="text-gray-600">|</span>
        {pointOpts.length > 0 && (
          <Dropdown value={selPoint} opts={pointOpts} onChange={(v) => setSelPoint(v)} />
        )}
      </div>

      {/* KPI Stats (4 columns) */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        <StatCard label="当前值" value={latest} unit={ptUnit} color={ptColor} decimals={2} />
        <StatCard label="24h均值" value={mean} unit={ptUnit} color="text-gray-200" decimals={2} />
        <StatCard label="24h峰值" value={max} unit={ptUnit} color={max > mean * 1.3 ? 'text-red-400' : 'text-gray-200'} decimals={2} />
        <StatCard label="24h谷值" value={min} unit={ptUnit} color="text-gray-200" decimals={2} />
      </div>

      {/* Main Trend Chart */}
      <div className="glass rounded-lg p-4 mb-5">
        <div className="flex items-center justify-between mb-3">
          <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>
            {METRIC_LABELS[selPoint] || selPoint} 趋势（{TIME_RANGE_OPTS.find(o => o.value === timeRange)?.label || timeRange + '分'}）
          </div>
          <TimeRangeSel value={timeRange} onChange={(v) => { setTimeRange(v); loadFull(v); }} />
        </div>
        <div ref={trendRef} style={{ width: '100%', height: 300 }} />
      </div>

      {/* Dual Charts: Distribution + Scatter */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div className="glass rounded-lg p-4">
          <div className={`text-xs ${M} uppercase tracking-wider mb-2 ${H}`}>数值分布</div>
          <div ref={distRef} style={{ width: '100%', height: 240 }} />
        </div>
        <div className="glass rounded-lg p-4">
          <div className={`text-xs ${M} uppercase tracking-wider mb-2 ${H}`}>关联指标 <span className="lowercase text-gray-600">(采样显示)</span></div>
          <div ref={scatterRef} style={{ width: '100%', height: 240 }} />
        </div>
      </div>

      {/* Radar Chart */}
      <div className="glass rounded-lg p-4 mb-5">
        <div className={`text-xs ${M} uppercase tracking-wider mb-2 ${H}`}>全点位实时雷达图</div>
        <div ref={radarRef} style={{ width: '100%', height: 300 }} />
      </div>

      {/* Point List */}
      <div className="flex items-center justify-between mb-3">
        <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>采集点位列表</div>
        <div className={`text-[0.7rem] ${M} ${B}`}>点击点位进入详情 →</div>
      </div>
      <div className="glass rounded-lg overflow-hidden">
        {tree.length === 0 && points.length === 0 ? (
          <div className={`text-gray-600 text-sm py-8 text-center ${B}`}>加载中...</div>
        ) : points.length > 0 ? (
          <table className="w-full text-sm">
            <thead className="bg-[#0a0f18]">
              <tr className={`text-gray-500 text-[0.7rem] border-b border-gray-800/50 ${H}`}>
                <th className="py-2.5 px-4 text-left font-semibold">点位名称</th>
                <th className="py-2.5 px-4 text-left font-semibold">指标类型</th>
                <th className="py-2.5 px-4 text-right font-semibold">当前值</th>
                <th className="py-2.5 px-4 text-left font-semibold">单位</th>
                <th className="py-2.5 px-4 text-right font-semibold w-10"><span className="sr-only">操作</span></th>
              </tr>
            </thead>
            <tbody>
              {points.map((p: any, i: number) => {
                const metricColor = POINT_COLORS[p.metric] || '#3b82f6';
                const val = p.value != null ? Number(p.value) : null;
                return (
                  <tr
                    key={p.point_id || i}
                    onClick={() => onNavigatePoint(p.metric)}
                    className="border-b border-gray-800/30 last:border-0 hover:bg-white/[0.03] cursor-pointer transition-colors duration-150 group"
                  >
                    <td className="py-2.5 px-4">
                      <span className={`text-xs text-gray-300 ${B} group-hover:text-gray-200 transition-colors`}>
                        {p.label || p.point_id || '--'}
                      </span>
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="text-xs text-gray-500 font-body">
                        {METRIC_LABELS[p.metric] || p.metric}
                      </span>
                    </td>
                    <td className={`py-2.5 px-4 text-right text-xs ${K} tabular-nums`} style={{ color: metricColor }}>
                      {val != null ? val.toFixed(2) : '--'}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="text-xs text-gray-500 font-data">{p.unit || '--'}</span>
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <span className="text-xs text-gray-600 group-hover:text-blue-400 transition-colors pointer-events-none">▶</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : combined?.metrics ? (
          <table className="w-full text-sm">
            <thead className="bg-[#0a0f18]">
              <tr className={`text-gray-500 text-[0.7rem] border-b border-gray-800/50 ${H}`}>
                <th className="py-2.5 px-4 text-left font-semibold">指标</th>
                <th className="py-2.5 px-4 text-right font-semibold">当前值</th>
                <th className="py-2.5 px-4 text-left font-semibold">单位</th>
                <th className="py-2.5 px-4 text-right font-semibold w-10"><span className="sr-only">操作</span></th>
              </tr>
            </thead>
            <tbody>
              {combined.metrics.map((m: string) => {
                const vals = combined.series?.[m] || [];
                const latest = vals.length > 0 ? vals[vals.length - 1] : null;
                const metricColor = POINT_COLORS[m] || '#3b82f6';
                const unit = METRIC_UNITS[m] || '';
                return (
                  <tr
                    key={m}
                    onClick={() => onNavigatePoint(m)}
                    className="border-b border-gray-800/30 last:border-0 hover:bg-white/[0.03] cursor-pointer transition-colors duration-150 group"
                  >
                    <td className="py-2.5 px-4">
                      <span className={`text-xs text-gray-300 ${B} group-hover:text-gray-200 transition-colors`}>
                        {METRIC_LABELS[m] || m}
                      </span>
                    </td>
                    <td className={`py-2.5 px-4 text-right text-xs ${K} tabular-nums`} style={{ color: metricColor }}>
                      {latest != null ? Number(latest).toFixed(2) : '--'}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="text-xs text-gray-500 font-data">{unit}</span>
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <span className="text-xs text-gray-600 group-hover:text-blue-400 transition-colors pointer-events-none">▶</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className={`text-gray-600 text-sm py-8 text-center ${B}`}>该设备暂无采集点位</div>
        )}
      </div>
    </>
  );
}
