import { useNavigationStore, type Level, type TabType } from '../../store/navigationStore';
import { useAppStore } from '../../store/useProjectStore';
import { H, B, M } from '../../utils/dashboard';

/* ── 层级导航项配置 ── */
const HIERARCHY_ITEMS: { level: Level; tab: TabType; label: string; icon: string }[] = [
  {
    level: 'project', tab: 'projectOverview', label: '项目概览',
    icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z',
  },
  {
    level: 'workshop', tab: 'workshopOverview', label: '车间概览',
    icon: 'M22 22H2V10l10-8 10 8v12zM12 5.5L4 12v8h16v-8l-8-6.5zM8 18h2v-4H8v4zm4 0h2v-6h-2v6zm4 0h2v-2h-2v2z',
  },
  {
    level: 'device', tab: 'deviceOverview', label: '设备概览',
    icon: 'M22 2H2v16h6l-2 4h12l-2-4h6V2zm-8 16h-4v-2h4v2zm6-4H4V4h16v10z',
  },
  {
    level: 'point', tab: 'pointOverview', label: '点位概览',
    icon: 'M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z',
  },
];

const FUNC_ITEMS: { tab: TabType; label: string; icon: string }[] = [
  { tab: 'analytics', label: '数据分析', icon: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z' },
  { tab: 'governance', label: '数据治理', icon: 'M12 2l-8 8h2v8h5v-6h2v6h5v-8h2L12 2zm-1 14H7v-4h4v4z' },
  { tab: 'reports', label: '报告管理', icon: 'M14 2H6C4.9 2 4.01 2.9 4.01 4L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 14H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z' },
];

/** Clear context at and below a level — sidebar click = aggregate view */
function clearContextAt(level: Level) {
  const app = useAppStore.getState();
  switch (level) {
    case 'project':
      app.setCurrentWorkshop(null);
      app.setCurrentDevice(null);
      app.setCurrentPoint(null);
      break;
    case 'workshop':
      app.setCurrentWorkshop(null);
      app.setCurrentDevice(null);
      app.setCurrentPoint(null);
      break;
    case 'device':
      app.setCurrentDevice(null);
      app.setCurrentPoint(null);
      break;
    case 'point':
      app.setCurrentPoint(null);
      break;
  }
}

export default function DynamicSidebar() {
  const activeTab = useNavigationStore(s => s.activeTab);
  const goToLevel = useNavigationStore(s => s.goToLevel);
  const setActiveTab = useNavigationStore(s => s.setActiveTab);
  return (
    <nav className="w-52 flex-shrink-0 bg-[#0a0f18] border-r border-[#1a2440] flex flex-col py-3">
      {/* ── 层级导航区 ── */}
      <div className={`px-4 py-2 text-[0.7rem] ${M} uppercase tracking-[0.12em] ${H}`}>
        层级导航
      </div>
      {HIERARCHY_ITEMS.map(item => {
        const isActive = activeTab === item.tab;

        return (
          <div
            key={item.tab}
            onClick={() => { clearContextAt(item.level); goToLevel(item.level); }}
            role="button" aria-label={item.label}
            className={`flex items-center gap-3 px-4 py-2.5 mx-2 rounded transition-all duration-200 text-sm select-none ${
              isActive
                ? 'bg-[#162240] text-gray-200 shadow-[inset_0_1px_0_rgba(59,130,246,0.2)] cursor-pointer'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#0e1628] active:bg-[#111d33] cursor-pointer'
            } ${B}`}
          >
            {/* Icon */}
            <svg viewBox="0 0 24 24" fill="currentColor" className={`w-4 h-4 flex-shrink-0 transition-opacity duration-200 ${
              isActive ? 'opacity-100' : 'opacity-50'
            }`}>
              <path d={item.icon} />
            </svg>
            <span className="flex-1">{item.label}</span>
            {isActive && (
              <span className="w-1 h-4 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
            )}
          </div>
        );
      })}

      {/* ── 分隔线 ── */}
      <div className="mx-4 my-3 border-t border-[#1a2440]" />

      {/* ── 功能页面区 ── */}
      <div className={`px-4 py-2 text-[0.7rem] ${M} uppercase tracking-[0.12em] ${H}`}>
        功能页面
      </div>
      {FUNC_ITEMS.map(item => {
        const isActive = activeTab === item.tab;
        return (
          <div
            key={item.tab}
            onClick={() => { clearContextAt('project'); setActiveTab(item.tab); }}
            role="button" aria-label={item.label}
            className={`flex items-center gap-3 px-4 py-2.5 mx-2 rounded cursor-pointer transition-all duration-200 text-sm select-none ${
              isActive
                ? 'bg-[#162240] text-gray-200 shadow-[inset_0_1px_0_rgba(59,130,246,0.2)]'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#0e1628] active:bg-[#111d33]'
            } ${B}`}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className={`w-4 h-4 flex-shrink-0 ${isActive ? 'opacity-100' : 'opacity-50'}`}>
              <path d={item.icon} />
            </svg>
            <span className="flex-1">{item.label}</span>
            {isActive && (
              <span className="w-1 h-4 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
            )}
          </div>
        );
      })}

      {/* ── 返回总览 ── */}
      <div className="mt-auto mx-2 pt-3 border-t border-[#1a2440]">
        <div
          onClick={() => {
            useAppStore.getState().setCurrentProject(null);
            useNavigationStore.getState().reset();
          }}
          role="button" aria-label="返回总览"
          className={`flex items-center gap-3 px-4 py-2.5 rounded cursor-pointer text-sm text-gray-500 hover:text-gray-300 hover:bg-[#0e1628] transition-all duration-200 ${B}`}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 flex-shrink-0 opacity-50">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
          </svg>
          返回总览
        </div>
      </div>

    </nav>
  );
}
