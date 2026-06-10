import { useEffect, useRef, useState, useCallback } from 'react';
import echarts from '../../echarts-setup';
import { ProjectOverview } from '../../api/projects';
import { WORKSHOP_NAMES, WORKSHOP_PROJECT, PROJECT_NAMES, PROJECT_COLORS } from '../../utils/dashboard';

interface ChinaMapProps {
  projects: ProjectOverview[];
  onProjectClick: (project: ProjectOverview) => void;
}

const PCFG: Record<string, { provinces: string[]; center: [number, number]; neon: string }> = {
  'project-huadong': { provinces: ['广东省', '江苏省', '浙江省'], center: [118, 32], neon: '#0ea5e9' },
  'project-beifang': { provinces: ['山东省', '天津市', '辽宁省'], center: [118, 38], neon: '#f97316' },
  'project-xinan': { provinces: ['四川省', '重庆市', '云南省'], center: [104, 28], neon: '#22c55e' },
};

const WS: { name: string; lng: number; lat: number }[] = [
  { name: '深圳', lng: 114.0579, lat: 22.5431 },
  { name: '苏州', lng: 120.5853, lat: 31.2990 },
  { name: '杭州', lng: 120.1551, lat: 30.2741 },
  { name: '青岛', lng: 120.3826, lat: 36.0671 },
  { name: '天津', lng: 117.2009, lat: 39.0842 },
  { name: '大连', lng: 121.6147, lat: 38.9140 },
  { name: '成都', lng: 104.0668, lat: 30.5728 },
  { name: '重庆', lng: 106.9123, lat: 29.4316 },
  { name: '昆明', lng: 102.7183, lat: 25.0389 },
];

// city name → workshop id mapping
const CITY_WS_ID: Record<string, string> = {
  '深圳': 'workshop-sz', '苏州': 'workshop-szh', '杭州': 'workshop-hz',
  '青岛': 'workshop-qd', '天津': 'workshop-tj', '大连': 'workshop-dl',
  '成都': 'workshop-cd', '重庆': 'workshop-cq', '昆明': 'workshop-km',
};

export default function ChinaMap({ projects, onProjectClick }: ChinaMapProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const outerRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);
  const readyRef = useRef(false);
  const projectsRef = useRef(projects);
  const clickRef = useRef(onProjectClick);
  projectsRef.current = projects;
  clickRef.current = onProjectClick;

  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 });
  const [isDragging, setIsDragging] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1.25);
  const zoomRef = useRef(1.25);

  const onMove = useCallback((e: React.MouseEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    setMouse({ x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height });
  }, []);

  const onMouseDown = useCallback(() => setIsDragging(true), []);
  const onMouseUp = useCallback(() => setIsDragging(false), []);

  // listen for global mouseup to reset drag state
  useEffect(() => {
    const up = () => setIsDragging(false);
    window.addEventListener('mouseup', up);
    return () => window.removeEventListener('mouseup', up);
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;
    const inst = echarts.init(chartRef.current, 'dark');
    instanceRef.current = inst;

    fetch('https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json')
      .then(r => r.json())
      .then(geo => {
        echarts.registerMap('china', geo);
        readyRef.current = true;
        draw(inst);
      })
      .catch(e => console.error('Map load failed', e));

    const rs = () => inst.resize();
    window.addEventListener('resize', rs);

    inst.on('click', (p: any) => {
      let hit: ProjectOverview | undefined;
      if (p.seriesType === 'effectScatter' && p.name) {
        hit = projectsRef.current.find(x => x.name === p.name);
      } else if (p.name) {
        for (const x of projectsRef.current) {
          const c = PCFG[x.id];
          if (c?.provinces.includes(p.name)) { hit = x; break; }
        }
      }
      if (hit) clickRef.current(hit);
    });

    // track zoom level from ECharts roam events
    inst.on('georoam', (params: any) => {
      if (params.zoom) {
        const opt = inst.getOption() as any;
        const z = opt.geo?.[0]?.zoom;
        if (z != null && z !== zoomRef.current) {
          zoomRef.current = z;
          setZoomLevel(z);
        }
      }
      // drag boundary clamping
      if (!params.zoom) {
        const opt = inst.getOption() as any;
        const c: number[] = opt.geo?.[0]?.center;
        if (c) {
          const clamped = [
            Math.min(140, Math.max(70, c[0])),
            Math.min(55, Math.max(15, c[1])),
          ];
          if (c[0] !== clamped[0] || c[1] !== clamped[1]) {
            inst.setOption({ geo: { center: clamped } });
          }
        }
      }
    });

    return () => { window.removeEventListener('resize', rs); inst.dispose(); };
  }, []);

  // incremental data update — preserve view state
  useEffect(() => {
    const inst = instanceRef.current;
    if (!readyRef.current || !inst) return;
    const projs = projectsRef.current;
    const regs: any[] = [];
    projs.forEach(p => {
      const c = PCFG[p.id];
      if (!c) return;
      c.provinces.forEach(pv => regs.push({
        name: pv,
        itemStyle: { areaColor: c.neon + '33', borderColor: c.neon + '99', borderWidth: 1.5 },
        emphasis: { itemStyle: { areaColor: c.neon + '66', borderColor: c.neon, borderWidth: 2 } },
      }));
    });
    const ps = projs.map(p => { const c = PCFG[p.id]; return { name: p.name, value: c ? [...c.center, 24] : [110, 35, 20], itemStyle: { color: c?.neon } }; });
    inst.setOption({
      geo: { regions: regs },
      series: [{ data: ps }],
    }, false);
  }, [projects]);

  function draw(inst: echarts.ECharts) {
    const projs = projectsRef.current;
    const regs: any[] = [];
    projs.forEach(p => {
      const c = PCFG[p.id];
      if (!c) return;
      c.provinces.forEach(pv => regs.push({
        name: pv,
        itemStyle: { areaColor: c.neon + '33', borderColor: c.neon + '99', borderWidth: 1.5 },
        emphasis: { itemStyle: { areaColor: c.neon + '66', borderColor: c.neon, borderWidth: 2 } },
      }));
    });

    function projCard(pp: ProjectOverview) {
      const c = PCFG[pp.id];
      const accent = c?.neon || '#3b82f6';
      return [
        `<div style="padding:2px 0;font-size:15px;font-weight:700;color:#fff;margin-bottom:8px"><span style="display:inline-block;width:8px;height:8px;background:${accent};margin-right:8px"></span>${pp.name}</div>`,
        `<table style="width:100%;border-collapse:collapse;font-size:12px">`,
        `<tr><td style="color:#94a3b8;padding:2px 0">车间数</td><td style="text-align:right;color:#e2e8f0;font-weight:600">${pp.workshop_count}</td></tr>`,
        `<tr><td style="color:#94a3b8;padding:2px 0">设备数</td><td style="text-align:right;color:#e2e8f0;font-weight:600">${pp.device_count}</td></tr>`,
        `<tr><td style="color:#94a3b8;padding:2px 0">采集点位</td><td style="text-align:right;color:#e2e8f0;font-weight:600">${pp.point_count}</td></tr>`,
        `<tr><td style="color:#94a3b8;padding:2px 0">运行效率</td><td style="text-align:right;color:${accent};font-weight:700;font-size:14px">${pp.oee_avg.toFixed(1)}%</td></tr>`,
        `</table>`,
        `<div style="border-top:1px solid #1e3050;margin-top:6px;padding-top:6px;font-size:11px;color:#64748b">`,
        `效率参数: 产量计数 · 不良品数 · 良品率 · OEE · 节拍时间`,
        `</div>`,
      ].join('');
    }

    function workshopCard(cityName: string) {
      const wsId = CITY_WS_ID[cityName];
      const wsName = WORKSHOP_NAMES[wsId] || cityName;
      const pid = WORKSHOP_PROJECT[wsId];
      const accent = PCFG[pid]?.neon || PROJECT_COLORS[pid] || '#64748b';
      const projectName = PROJECT_NAMES[pid] || pid || '';
      return [
        `<div style="padding:2px 0;font-size:15px;font-weight:700;color:#fff;margin-bottom:8px"><span style="display:inline-block;width:8px;height:8px;background:${accent};margin-right:8px"></span>${wsName}</div>`,
        `<table style="width:100%;border-collapse:collapse;font-size:12px">`,
        `<tr><td style="color:#94a3b8;padding:2px 0">所属项目</td><td style="text-align:right;color:${accent};font-weight:600">${projectName}</td></tr>`,
        `<tr><td style="color:#94a3b8;padding:2px 0">所在城市</td><td style="text-align:right;color:#e2e8f0;font-weight:600">${cityName}</td></tr>`,
        `</table>`,
        `<div style="border-top:1px solid #1e3050;margin-top:6px;padding-top:6px;font-size:11px;color:#64748b">`,
        `点击进入项目详情查看车间实时数据`,
        `</div>`,
      ].join('');
    }

    // ONE unified formatter — used by both global tooltip (series) and geo tooltip (regions)
    const fmt = (ps: any) => {
      const projs = projectsRef.current;
      // 1) project effectScatter point by name
      const pp = projs.find(x => x.name === ps.name);
      if (pp) return projCard(pp);
      // 2) geo region → match province to project
      for (const x of projs) {
        const c = PCFG[x.id];
        if (c?.provinces.includes(ps.name)) return projCard(x);
      }
      // 3) workshop city scatter point
      if (CITY_WS_ID[ps.name]) return workshopCard(ps.name);
      // 4) fallback
      return ps.name ? `<span style="color:#e2e8f0;font-size:13px">${ps.name}</span>` : '';
    };

    const tipStyle = {
      backgroundColor: '#0a0e18',
      borderColor: '#1e3050',
      borderWidth: 1,
      padding: [12, 16],
      textStyle: { color: '#e2e8f0', fontSize: 13 },
      extraCssText: 'border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,0.6);',
    };

    inst.setOption({
      tooltip: { trigger: 'item', ...tipStyle, formatter: fmt },
      backgroundColor: 'transparent',
      geo: {
        map: 'china', roam: true, zoom: 1.25, center: [105, 36], aspectScale: 0.85,
        scaleLimit: { min: 0.8, max: 8 },
        label: { show: false },
        itemStyle: { areaColor: '#0a1420', borderColor: '#1e3048', borderWidth: 0.8 },
        emphasis: { label: { show: false }, itemStyle: { areaColor: '#162a44' } },
        regions: regs, silent: false,
        tooltip: { show: true, ...tipStyle, formatter: fmt },
      },
      series: [
        {
          type: 'effectScatter', coordinateSystem: 'geo',
          data: projs.map(p => { const c = PCFG[p.id]; return { name: p.name, value: c ? [...c.center, 24] : [110, 35, 20], itemStyle: { color: c?.neon } }; }),
          symbolSize: 20, rippleEffect: { brushType: 'stroke', scale: 3, period: 3 }, zlevel: 2,
          label: { show: true, formatter: '{b}', position: 'bottom', distance: 14, color: '#e2e8f0', fontSize: 14, fontWeight: 700, fontFamily: 'Inter' },
        },
        {
          type: 'scatter', coordinateSystem: 'geo',
          data: WS.map(w => ({ name: w.name, value: [w.lng, w.lat, 8], itemStyle: { color: '#64748b' } })),
          symbolSize: 8, zlevel: 1,
          label: { show: true, formatter: '{b}', position: 'right', distance: 4, color: '#f3f4f6', fontSize: 10, fontFamily: 'Inter' },
        },
      ],
    });
  }

  // parallax — zoom-responsive: stronger depth effect when zoomed in
  const zoomFactor = Math.min(zoomLevel / 1.25, 3);
  const ox = (mouse.x - 0.5) * 24 * zoomFactor;
  const oy = (mouse.y - 0.5) * 24 * zoomFactor;
  const rx = (mouse.y - 0.5) * 8 * zoomFactor;
  const ry = (mouse.x - 0.5) * 8 * zoomFactor;
  const px = 50 + (mouse.x - 0.5) * 16;
  const py = 48 + (mouse.y - 0.5) * 16;

  return (
    <div
      ref={outerRef}
      className="relative"
      onMouseMove={onMove}
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}
      style={{ width: '100%', height: '100%', perspective: `${1800 / zoomFactor}px`, perspectiveOrigin: `${px}% ${py}%` }}
    >
      <div
        ref={chartRef}
        className="map-parallax"
        style={{
          width: '100%',
          height: '100%',
          transform: `translateX(${ox}px) translateY(${oy}px) rotateX(${6 + rx}deg) rotateY(${-2 + ry}deg) scale(1.03)`,
          cursor: isDragging ? 'grabbing' : 'grab',
        }}
      />

      {/* zoom level badge */}
      <div className="absolute bottom-3 left-3 z-10 pointer-events-none">
        <span className="map-zoom-badge">
          {Math.round(zoomLevel * 100)}%
        </span>
      </div>
    </div>
  );
}
