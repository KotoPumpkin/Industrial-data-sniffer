import { apiFetch } from './client';

export interface ServiceStatus {
  name: string;
  status: string;
  port: number;
  url?: string;
}

export function getSystemStatus() {
  return apiFetch<ServiceStatus[]>('/api/system/status');
}

export function getCurrentUser() {
  return apiFetch<{ authenticated: boolean; username?: string; role?: string }>('/api/auth/current');
}

export async function logout() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  window.location.href = '/login';
}
