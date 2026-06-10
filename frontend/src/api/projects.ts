import { apiFetch } from './client';

export interface ProjectOverview {
  id: string;
  name: string;
  color: string;
  center_lat: number;
  center_lng: number;
  workshop_count: number;
  device_count: number;
  point_count: number;
  online_devices: number;
  active_alerts: number;
  production_count: number;
  oee_avg: number;
}

export interface ProjectStats {
  online_devices: number;
  active_alerts: number;
  anomaly_count: number;
  workshop_count: number;
}

export function getProjectsOverview() {
  return apiFetch<ProjectOverview[]>('/api/projects/overview');
}

export function getProjectStats(projectId: string) {
  return apiFetch<ProjectStats>(`/api/projects/${projectId}/stats`);
}

export function getWorkshops(projectId?: string) {
  const q = projectId ? `?project_id=${projectId}` : '';
  return apiFetch<any[]>(`/api/workshops${q}`);
}
