import { create } from 'zustand';

export type Level = 'project' | 'workshop' | 'device' | 'point';
export type TabType =
  | 'projectOverview' | 'workshopOverview' | 'deviceOverview' | 'pointOverview'
  | 'analytics' | 'governance' | 'reports';

const TAB_TO_LEVEL: Record<TabType, Level> = {
  projectOverview: 'project', workshopOverview: 'workshop',
  deviceOverview: 'device', pointOverview: 'point',
  analytics: 'project', governance: 'project', reports: 'project',
};

const LEVEL_TO_TAB: Record<Level, TabType> = {
  project: 'projectOverview', workshop: 'workshopOverview',
  device: 'deviceOverview', point: 'pointOverview',
};

interface NavigationState {
  level: Level;
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  goToLevel: (level: Level) => void;
  drillTo: (level: 'workshop' | 'device' | 'point') => void;
  reset: () => void;
}

export const useNavigationStore = create<NavigationState>((set) => ({
  level: 'project',
  activeTab: 'projectOverview',

  setActiveTab: (tab) => set({ activeTab: tab, level: TAB_TO_LEVEL[tab] }),

  goToLevel: (level) => {
    set({ level, activeTab: LEVEL_TO_TAB[level] });
  },

  drillTo: (level) => {
    set({
      level,
      activeTab: LEVEL_TO_TAB[level],
    });
  },

  reset: () => set({
    level: 'project', activeTab: 'projectOverview',
  }),
}));
