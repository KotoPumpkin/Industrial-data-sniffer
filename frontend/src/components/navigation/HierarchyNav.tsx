import React, { useMemo } from 'react';
import { useAppStore } from '../../store/useProjectStore';
import { useNavigationStore, type Level } from '../../store/navigationStore';
import { PROJECT_NAMES, WORKSHOP_NAMES, deviceStatus, H, B, K } from '../../utils/dashboard';
import { useDeviceTree } from '../../hooks/useDeviceTree';

export default React.memo(function HierarchyNav() {
  const pid = useAppStore(s => s.currentProjectId);
  const wid = useAppStore(s => s.currentWorkshopId);
  const did = useAppStore(s => s.currentDeviceId);
  const ptid = useAppStore(s => s.currentPointId);

  const level = useNavigationStore(s => s.level);
  const goToLevel = useNavigationStore(s => s.goToLevel);

  const setWorkshop = useAppStore(s => s.setCurrentWorkshop);
  const setDevice = useAppStore(s => s.setCurrentDevice);
  const setPoint = useAppStore(s => s.setCurrentPoint);

  const tree = useDeviceTree(pid);

  // ── Breadcrumb segments ──
  const segments: { label: string; level: Level; active: boolean }[] = [];
  if (pid) segments.push({ label: PROJECT_NAMES[pid] || pid, level: 'project', active: level === 'project' });
  if (wid) segments.push({ label: WORKSHOP_NAMES[wid] || wid, level: 'workshop', active: level === 'workshop' });
  if (did) segments.push({ label: did, level: 'device', active: level === 'device' });
  if (ptid) segments.push({ label: ptid, level: 'point', active: level === 'point' });

  const handleClick = (segLevel: Level) => {
    switch (segLevel) {
      case 'project': setWorkshop(null); setDevice(null); setPoint(null); goToLevel('project'); break;
      case 'workshop': setDevice(null); setPoint(null); goToLevel('workshop'); break;
      case 'device': setPoint(null); goToLevel('device'); break;
      case 'point': goToLevel('point'); break;
    }
  };

  // ── Context stats (right side) ──
  const devInfo = did ? tree.find((d: any) => d.device_id === did) : null;

  const devFlat = devInfo ? (() => {
    const vals: any = {};
    (devInfo.points || []).forEach((p: any) => { if (p.value != null) vals[p.metric] = Number(p.value); });
    return { ...vals, name: devInfo.device_id };
  })() : null;

  const st = devFlat ? deviceStatus(devFlat) : 'ok';
  const stColor = st === 'alarm' ? 'bg-red-500' : st === 'warn' ? 'bg-orange-400' : 'bg-emerald-400';
  const stLabel = st === 'alarm' ? '告警' : st === 'warn' ? '异常' : '正常';

  const alarms = useMemo(() => tree.filter((d: any) => {
    const vals: any = {};
    (d.points || []).forEach((p: any) => { if (p.value != null) vals[p.metric] = Number(p.value); });
    return deviceStatus({ ...vals }) === 'alarm';
  }).length, [tree]);

  const mainValue = (() => {
    if (ptid && devInfo) {
      const p = (devInfo.points || []).find((x: any) => x.metric === ptid);
      if (p?.value != null) return `${Number(p.value).toFixed(1)}`;
    }
    return null;
  })();

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-[#0a0f18] border-b border-[#1a2440] min-h-[2.4rem]">
      {/* Left: breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs select-none flex-wrap">
        {segments.length === 0 ? (
          <span className={`text-gray-500 ${B}`}>未选择项目</span>
        ) : (
          segments.map((seg, i) => (
            <span key={seg.level} className="flex items-center gap-1.5">
              {i > 0 && (
                <svg viewBox="0 0 16 16" fill="none" className="w-3 h-3 text-gray-600 flex-shrink-0">
                  <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              <button
                onClick={() => handleClick(seg.level)}
                className={`transition-colors duration-200 truncate max-w-[160px] ${
                  seg.active ? 'text-blue-400 hover:text-blue-300' : 'text-gray-500 hover:text-gray-300'
                } ${H}`}
                title={seg.label}
                type="button"
              >
                {seg.label}
              </button>
            </span>
          ))
        )}
      </div>

      {/* Right: context stats */}
      <div className="flex items-center gap-3 text-[0.65rem] flex-shrink-0">
        {alarms > 0 && (
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            <span className={`${K} text-red-400`}>{alarms} 告警</span>
          </span>
        )}
        {mainValue && (
          <span className={`${K} text-gray-300`}>{mainValue}</span>
        )}
        {did && (
          <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#111827] border border-[#1a2440]">
            <span className={`w-1.5 h-1.5 rounded-full ${stColor}`} />
            <span className={`${B} text-gray-400`}>{stLabel}</span>
          </span>
        )}
        <span className={`${B} text-gray-600`}>{tree.length} 设备</span>
      </div>
    </div>
  );
});
