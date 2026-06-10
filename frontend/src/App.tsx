import { AnimatePresence } from 'framer-motion';
import { useAppStore } from './store/useProjectStore';
import { useNavigationStore } from './store/navigationStore';
import { useEffect } from 'react';
import { getCurrentUser } from './api/system';
import { prefersReducedMotion } from './utils/dashboard';
import Home from './pages/Home';
import Project from './pages/Project';

function Topbar() {
  const username = useAppStore((s) => s.username);
  const currentProjectId = useAppStore((s) => s.currentProjectId);
  const setCurrentProject = useAppStore((s) => s.setCurrentProject);

  return (
    <header className="h-[3.2rem] bg-[#161a22] border-b border-[#232830] flex items-center justify-between px-5 z-50">
      <div className="flex items-center gap-3">
        {currentProjectId && (
          <button
            onClick={() => {
              useNavigationStore.getState().reset();
              setCurrentProject(null);
            }}
            className="text-gray-500 hover:text-gray-300 transition text-sm"
          >
            ← 返回
          </button>
        )}
        <img src="/logo.png" alt="Logo" className="h-[2rem] w-auto" />
        <span className="text-[0.95rem] font-heading font-semibold text-gray-200">
          工业数据采集管理平台
        </span>
      </div>
      <div className="flex items-center gap-4">
        {!currentProjectId && (
          <span className="hint-badge">
            滚轮缩放 · 按住拖拽 · 点击项目区域进入项目概览
          </span>
        )}
        <span className="text-xs text-gray-500 font-body">{username}</span>
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }).then(
              () => (window.location.href = '/login')
            );
          }}
          className="text-xs text-gray-500 hover:text-gray-300 transition font-body"
        >
          退出
        </a>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.4)]" />
          在线
        </div>
      </div>
    </header>
  );
}

export default function App() {
  const currentProjectId = useAppStore((s) => s.currentProjectId);
  const setAuth = useAppStore((s) => s.setAuth);

  useEffect(() => {
    getCurrentUser().then((data) => {
      if (!data.authenticated) {
        window.location.href = '/login';
      } else if (data.username) {
        setAuth(data.username);
      }
    }).catch(() => {
      window.location.href = '/login';
    });
  }, [setAuth]);

  return (
    <div className="min-h-screen bg-[#080b10] text-gray-200">
      <Topbar />
      <main className="h-[calc(100vh-3.2rem)] overflow-hidden">
        {prefersReducedMotion() ? (
          currentProjectId ? <Project key="project" /> : <Home key="home" />
        ) : (
          <AnimatePresence mode="wait">
            {currentProjectId ? (
              <Project key="project" />
            ) : (
              <Home key="home" />
            )}
          </AnimatePresence>
        )}
      </main>
    </div>
  );
}
