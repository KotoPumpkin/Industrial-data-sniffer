import { useState, useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '../../store/useProjectStore';
import { useNavigationStore } from '../../store/navigationStore';
import { useDeviceTree } from '../../hooks/useDeviceTree';
import { H, B, K, M, Dropdown, TimeRangeSel, TIME_RANGE_OPTS, useChart, Tbl, METRIC_LABELS, METRIC_UNITS, WORKSHOP_NAMES, POLL_INTERVAL, DATA_FETCH_MINUTES, getTrendDataZoom, updateChartSeries } from '../../utils/dashboard';
import StatCard from '../../components/ui/StatCard';
import echarts from '../../echarts-setup';

interface Props {}

const POINT_COLORS: Record<string, string> = {
  temperature: '#f87171', vibration: '#fb923c', rpm: '#3b82f6', power: '#34d399',
  feed_rate: '#a78bfa', voltage: '#fbbf24', current: '#22d3ee',
  humidity: '#3b82f6', pressure: '#a78bfa', flow_rate: '#22d3ee',
  count: '#3b82f6', defect_count: '#f87171', quality_rate: '#34d399', oee: '#3b82f6', cycle_time: '#fb923c',
};

export default function PointOverview(_props: Props) {
  const pid = useAppStore(s => s.currentProjectId);
  const did = useAppStore(s => s.currentDeviceId);
  const ptid = useAppStore(s => s.currentPointId);
  const tree = useDeviceTree(pid);
  const [report, setReport] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [trendInfo, setTrendInfo] = useState<any>(null);
  const [selMetric, setSelMetric] = useState(ptid || 'temperature');
  const [timeRange, setTimeRange] = useState(DATA_FETCH_MINUTES);
  const timeRangeRef = useRef(timeRange);
  timeRangeRef.current = timeRange;
  const trendRef = useRef<HTMLDivElement>(null);
  const trendChart = useChart(trendRef);
  const firstTrend = useRef(true);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  const devInfo = tree.find(d => d.device_id === did);
  const points = devInfo?.points || [];

  // Build point selector — deduplicate by metric, show count when multiple points share same metric
  const metricOpts = (() => {
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

  // ── Merged point detail (history + anomalies + trend + report) ──
  const loadPointDetail = useCallback(async (m: string, rangeMinutes: number = DATA_FETCH_MINUTES) => {
    if (!did) return;
    try {
      const r = await fetch(`/api/metrics/point_detail?metric=${m}&device=${did}&minutes=${rangeMinutes}`, { credentials: 'include' });
      if (r.ok) {
        const data = await r.json();
        setHistory(data.history || []);
        setAnomalies(data.anomalies || []);
        setTrendInfo(data.trend_info || null);
        setReport(data.report || null);
      }
    } catch (e) { console.error('PointOverview loadPointDetail failed:', e); }
  }, [did]);

  // Initialize
  useEffect(() => {
    if (did) {
      loadPointDetail(selMetric);
    }
  }, [did, selMetric, loadPointDetail]);

  // ── Draw trend chart with anomaly markers ──
  useEffect(() => {
    if (!trendChart.current || !Array.isArray(history) || history.length === 0) return;
    const rawData: { time: string; value: number }[] = history.map((r: any) => ({
      time: r._time || '', value: Number(r._value || 0),
    })).sort((a, b) => a.time.localeCompare(b.time));

    if (rawData.length === 0) return;

    // Build anomaly mark points with short time labels (matching xAxis categories)
    const anomTimes = new Set(anomalies.map((a: any) => a.time?.slice(0, 19)));
    const markLineData: { xAxis: string }[] = [];
    rawData.forEach(p => {
      const ts = p.time?.slice(0, 19);
      if (anomTimes.has(ts)) markLineData.push({ xAxis: p.time?.slice(11, 19) || '' });
    });

    // Use index-based mapping: xAxis categories = xLabels, series data = values (no tuples)
    // This avoids category-name mismatch issues with ECharts + dataZoom
    const xLabels = rawData.map(p => p.time?.slice(11, 19) || '');
    const lineValues = rawData.map(p => p.value);

    const isFirst = firstTrend.current;

    if (isFirst) {
      // ── Full option: structural config + dataZoom slider ──
      trendChart.current.setOption({
        animation: true,
        tooltip: { trigger: 'axis', backgroundColor: '#0a0e18', borderColor: '#232830' },
        grid: { top: 8, right: 12, bottom: 44, left: 48 },
        xAxis: { type: 'category', data: xLabels, axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { show: false } },
        yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }, name: METRIC_UNITS[selMetric] || '', nameTextStyle: { color: '#64748b', fontSize: 10 } },
        dataZoom: getTrendDataZoom(timeRange),
        series: [{
          type: 'line', data: lineValues,
          smooth: true, symbol: 'none',
          connectNulls: false,
          lineStyle: { color: '#3b82f6', width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#3b82f630' }, { offset: 1, color: '#3b82f604' },
            ]),
          },
          markLine: markLineData.length > 0 ? {
            silent: true, symbol: 'none', data: markLineData.slice(0, 30),
            lineStyle: { color: '#f8717140', type: 'dotted', width: 1 },
          } : undefined,
        }],
      }, true); // notMerge: true — full replace on first render / metric change
    } else {
      // ── Data-only update: preserve dataZoom / grid / axes state ──
      const markLine = markLineData.length > 0 ? {
        silent: true, symbol: 'none', data: markLineData.slice(0, 30),
        lineStyle: { color: '#f8717140', type: 'dotted', width: 1 },
      } : undefined;
      updateChartSeries(trendChart.current, [{
        data: lineValues,
        markLine,
      }], xLabels);
    }

    firstTrend.current = false;
  }, [history, anomalies, trendChart, selMetric]);

  // ── Reset firstTrend on metric or timeRange change so chart gets full re-render ──
  useEffect(() => { firstTrend.current = true; }, [selMetric, timeRange]);

  // ── Polling (respects user-selected timeRange via ref) ──
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      if (did) { loadPointDetail(selMetric, timeRangeRef.current); }
    }, POLL_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [did, selMetric, loadPointDetail]);

  // Sync selMetric with ptid on mount
  useEffect(() => { if (ptid) setSelMetric(ptid); }, [ptid]);

  if (!pid) return null;

  // ── Aggregate view: all points across all devices ──
  if (!did || !ptid) {
    // Collect all points from all devices
    const allPoints: { device_id: string; wsId: string; metric: string; label: string; unit: string; value: number | null }[] = [];
    tree.forEach(d => {
      (d.points || []).forEach((p: any) => {
        allPoints.push({
          device_id: d.device_id,
          wsId: d.workshop || '',
          metric: p.metric,
          label: p.label || p.point_id || p.metric,
          unit: p.unit || '',
          value: p.value != null ? Number(p.value) : null,
        });
      });
    });
    // Group by metric
    const byMetric: Record<string, typeof allPoints> = {};
    allPoints.forEach(p => {
      if (!byMetric[p.metric]) byMetric[p.metric] = [];
      byMetric[p.metric].push(p);
    });
    const metricKeys = Object.keys(byMetric).sort((a, b) => byMetric[b].length - byMetric[a].length);
    const totalPoints = allPoints.length;
    const totalDevs = [...new Set(allPoints.map(p => p.device_id))].length;
    const alarmPoints = allPoints.filter(p => {
      if (p.metric === 'temperature' && p.value != null && p.value > 80) return true;
      if (p.metric === 'vibration' && p.value != null && p.value > 4.5) return true;
      return false;
    }).length;
    return (
      <>
        <h1 className={`text-2xl text-white ${H}`}>全部点位概况</h1>
        <p className={`text-sm text-gray-500 mb-5 ${B}`}>
          {totalDevs} 台设备 · {totalPoints} 个采集点位 · {metricKeys.length} 种指标
        </p>
        <div className="grid grid-cols-4 gap-3 mb-5">
          <StatCard label="点位总数" value={totalPoints} color="text-blue-400" />
          <StatCard label="指标类型" value={metricKeys.length} color="text-gray-200" />
          <StatCard label="涉及设备" value={totalDevs} color="text-gray-200" />
          <StatCard label="告警点位" value={alarmPoints} color={alarmPoints > 0 ? 'text-red-400' : 'text-green-400'} />
        </div>
        {metricKeys.map(metric => {
          const pts = byMetric[metric];
          const avgVal = pts.filter(p => p.value != null).reduce((s, p) => s + (p.value as number), 0);
          const count = pts.filter(p => p.value != null).length;
          const metricColor = POINT_COLORS[metric] || '#3b82f6';
          return (
            <div key={metric} className="mb-5">
              <div className="flex items-center justify-between mb-3">
                <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>
                  {METRIC_LABELS[metric] || metric} · {pts.length} 个测点
                  {count > 0 && <span className="ml-2 text-gray-500">均值 {(avgVal / count).toFixed(2)} {pts[0]?.unit || ''}</span>}
                </div>
                <div className={`text-[0.7rem] ${M} ${B}`}>点击测点进入聚焦视图 →</div>
              </div>
              <div className="glass rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-[#0a0f18]">
                    <tr className={`text-gray-500 text-[0.7rem] border-b border-gray-800/50 ${H}`}>
                      <th className="py-2.5 px-4 text-left font-semibold">设备</th>
                      <th className="py-2.5 px-4 text-left font-semibold">测点名称</th>
                      <th className="py-2.5 px-4 text-right font-semibold">当前值</th>
                      <th className="py-2.5 px-4 text-left font-semibold">单位</th>
                      <th className="py-2.5 px-4 text-left font-semibold">车间</th>
                      <th className="py-2.5 px-4 text-right w-10"><span className="sr-only">操作</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pts.map((p, i) => (
                      <tr
                        key={`${p.device_id}-${p.metric}-${i}`}
                        onClick={() => {
                          useAppStore.getState().setCurrentDevice(p.device_id);
                          useAppStore.getState().setCurrentPoint(p.metric);
                          useNavigationStore.getState().drillTo('point');
                        }}
                        className="border-b border-gray-800/30 last:border-0 hover:bg-white/[0.03] cursor-pointer transition-colors duration-150 group"
                      >
                        <td className="py-2.5 px-4">
                          <span className={`text-xs text-gray-300 ${B} group-hover:text-gray-200 transition-colors`}>
                            {p.device_id}
                          </span>
                        </td>
                        <td className="py-2.5 px-4">
                          <span className="text-xs text-gray-400 font-body">{p.label}</span>
                        </td>
                        <td className={`py-2.5 px-4 text-right text-xs ${K} tabular-nums`} style={{ color: metricColor }}>
                          {p.value != null ? p.value.toFixed(2) : '--'}
                        </td>
                        <td className="py-2.5 px-4">
                          <span className="text-xs text-gray-500 font-data">{p.unit || '--'}</span>
                        </td>
                        <td className="py-2.5 px-4">
                          <span className="text-[0.65rem] text-gray-600 font-body">
                            {WORKSHOP_NAMES[p.wsId] || p.wsId || '--'}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-right">
                          <span className="text-xs text-gray-600 group-hover:text-blue-400 transition-colors pointer-events-none">▶</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </>
    );
  }

  const ptStats = report?.metrics?.[selMetric];
  const mean = ptStats?.mean ?? 0;
  const min = ptStats?.min ?? 0;
  const max = ptStats?.max ?? 0;
  const std = ptStats?.std ?? 0;
  const cv = ptStats?.cv ?? 0;
  const latestVal = ptStats?.latest ?? 0;
  const ptUnit = METRIC_UNITS[selMetric] || '';
  const ptLabel = METRIC_LABELS[selMetric] || selMetric;
  const trendDir = trendInfo?.trend || 'stable';

  // Compute rise/fall indicator
  const change = trendInfo?.change_from_start ?? 0;
  const changePct = mean > 0 ? (change / mean * 100) : 0;

  // Build data table rows
  const historyRows = (() => {
    if (!Array.isArray(history)) return [];
    const rows: any[] = [];
    const anomTimes = new Set(anomalies.map((a: any) => a.time?.slice(0, 19)));
    for (let i = Math.max(0, history.length - 50); i < history.length; i++) {
      const r = history[i];
      const ts = r._time || '';
      const val = Number(r._value || 0);
      const prev = i > 0 ? Number(history[i - 1]._value || 0) : val;
      const rate = prev !== 0 ? ((val - prev) / Math.abs(prev) * 100) : 0;
      const isAnom = anomTimes.has(ts?.slice(0, 19));
      rows.push({
        cells: [ts?.slice(11, 19) || '', val.toFixed(3), rate > 0 ? `+${rate.toFixed(1)}%` : `${rate.toFixed(1)}%`, isAnom ? '⚠ 异常' : '--'],
        highlight: isAnom ? '#f87171' : undefined,
      });
    }
    return rows;
  })();

  return (
    <>
      {/* Title + Point Selector */}
      <div className="flex items-center gap-4 mb-5">
        <h1 className={`text-2xl text-white ${H}`}>{ptLabel}</h1>
        {metricOpts.length > 1 && (
          <Dropdown value={selMetric} opts={metricOpts} onChange={(v) => setSelMetric(v)} />
        )}
      </div>

      {/* Large Value Card */}
      <div className="glass rounded-lg p-6 mb-5 flex items-center justify-between">
        <div>
          <div className={`text-xs ${M} uppercase tracking-wider mb-1 ${H}`}>当前值</div>
          <div className="flex items-end gap-2">
            <span className={`text-4xl ${K} text-white`}>{latestVal.toFixed(2)}</span>
            <span className={`text-lg ${K} text-gray-500 mb-1`}>{ptUnit}</span>
            {trendDir !== 'stable' && (
              <span className={`text-sm ${K} mb-1.5 flex items-center gap-0.5 ${trendDir === 'rising' ? (selMetric === 'temperature' || selMetric === 'vibration' ? 'text-red-400' : 'text-green-400') : (selMetric === 'temperature' || selMetric === 'vibration' ? 'text-green-400' : 'text-red-400')}`}>
                {trendDir === 'rising' ? '↑' : '↓'} {Math.abs(changePct).toFixed(1)}%
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className={`text-xs ${M} uppercase tracking-wider mb-1 ${H}`}>趋势方向</div>
          <span className={`text-lg ${K} ${trendDir === 'rising' ? 'text-orange-400' : trendDir === 'falling' ? 'text-blue-400' : 'text-gray-400'}`}>
            {trendDir === 'rising' ? '上升' : trendDir === 'falling' ? '下降' : '平稳'}
          </span>
        </div>
      </div>

      {/* Trend Chart */}
      <div className="glass rounded-lg p-4 mb-5">
        <div className="flex items-center justify-between mb-3">
          <div className={`text-xs ${M} uppercase tracking-wider ${H}`}>
            {ptLabel} 趋势（{TIME_RANGE_OPTS.find(o => o.value === timeRange)?.label || timeRange + '分'}）
          </div>
          <div className="flex items-center gap-2">
            {metricOpts.length > 1 && (
              <Dropdown value={selMetric} opts={metricOpts} onChange={(v) => setSelMetric(v)} />
            )}
            <TimeRangeSel value={timeRange} onChange={(v) => { setTimeRange(v); loadPointDetail(selMetric, v); }} />
          </div>
        </div>
        <div ref={trendRef} style={{ width: '100%', height: 300 }} />
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-6 gap-3 mb-5">
        <StatCard label="均值" value={mean} unit={ptUnit} color="text-blue-400" decimals={2} />
        <StatCard label="最小值" value={min} unit={ptUnit} color="text-gray-200" decimals={2} />
        <StatCard label="最大值" value={max} unit={ptUnit} color="text-gray-200" decimals={2} />
        <StatCard label="标准差" value={std} color="text-gray-200" decimals={3} />
        <StatCard label="变异系数" value={cv} unit="%" color="text-gray-200" decimals={1} />
        <StatCard label="异常数" value={anomalies.length} color={anomalies.length > 0 ? 'text-red-400' : 'text-green-400'} />
      </div>

      {/* Data Table */}
      <div className="glass rounded-lg p-4">
        <div className={`text-xs ${M} uppercase tracking-wider mb-3 ${H}`}>历史数据</div>
        {historyRows.length > 0 ? (
          <Tbl h={['时间', '值', '变化率', '异常']} rows={historyRows} />
        ) : (
          <div className={`text-gray-600 text-sm py-4 text-center ${B}`}>加载中...</div>
        )}
      </div>
    </>
  );
}
