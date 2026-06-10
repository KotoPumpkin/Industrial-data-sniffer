import { create } from 'zustand';

interface AppState {
  currentProjectId: string | null;
  currentWorkshopId: string | null;
  currentDeviceId: string | null;
  currentPointId: string | null;
  pageSubtitle: string;
  isAuthenticated: boolean;
  username: string;
  setCurrentProject: (id: string | null) => void;
  setCurrentWorkshop: (id: string | null) => void;
  setCurrentDevice: (id: string | null) => void;
  setCurrentPoint: (id: string | null) => void;
  setPageSubtitle: (title: string) => void;
  setAuth: (username: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentProjectId: null,
  currentWorkshopId: null,
  currentDeviceId: null,
  currentPointId: null,
  pageSubtitle: '',
  isAuthenticated: false,
  username: '',
  setCurrentProject: (id) => set({ currentProjectId: id, currentWorkshopId: null, currentDeviceId: null, currentPointId: null, pageSubtitle: id ? '项目概览' : '' }),
  setCurrentWorkshop: (id) => set({ currentWorkshopId: id, currentDeviceId: null, currentPointId: null }),
  setCurrentDevice: (id) => set({ currentDeviceId: id, currentPointId: null }),
  setCurrentPoint: (id) => set({ currentPointId: id }),
  setPageSubtitle: (title) => set({ pageSubtitle: title }),
  setAuth: (username) => set({ isAuthenticated: true, username }),
}));
