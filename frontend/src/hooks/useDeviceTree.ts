import { useState, useEffect, useRef } from 'react';

// Module-level singleton: one fetch loop per projectId
interface Entry {
  tree: any[];
  refs: number;
  timer: ReturnType<typeof setInterval> | null;
  listeners: Set<() => void>;
}

const stores = new Map<string, Entry>();

async function fetchTree(projectId: string): Promise<any[]> {
  try {
    const r = await fetch(`/api/devices/tree?project_id=${projectId}`, { credentials: 'include' });
    if (r.ok) return r.json();
  } catch {}
  return [];
}

export function useDeviceTree(projectId: string | null) {
  const [tree, setTree] = useState<any[]>([]);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (!projectId) {
      setTree([]);
      return;
    }

    let entry = stores.get(projectId);
    if (!entry) {
      entry = { tree: [], refs: 0, timer: null, listeners: new Set() };
      stores.set(projectId, entry);

      const load = async () => {
        const e = stores.get(projectId);
        if (!e) return;
        const data = await fetchTree(projectId);
        e.tree = data;
        // Notify all consumers
        e.listeners.forEach(fn => fn());
      };

      // First fetch immediately, start polling after
      load().then(() => {
        const e = stores.get(projectId);
        if (e && !e.timer && e.refs > 0) {
          e.timer = setInterval(load, 1000);
        }
      });
    }

    entry.refs++;
    const entryRef = entry;

    // Subscribe to updates
    const listener = () => {
      if (mountedRef.current) {
        setTree([...entryRef.tree]);
      }
    };
    entryRef.listeners.add(listener);

    // Use current cached tree immediately
    setTree([...entryRef.tree]);

    return () => {
      entryRef.listeners.delete(listener);
      entryRef.refs--;
      if (entryRef.refs <= 0) {
        if (entryRef.timer) {
          clearInterval(entryRef.timer);
          entryRef.timer = null;
        }
        stores.delete(projectId);
      }
    };
  }, [projectId]);

  return tree;
}
