import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useState, useEffect } from 'react';
import api from '../services/api';
import {
  LayoutDashboard, Trophy, Users, Brain, LogOut, Zap,
  CalendarDays, TableProperties, UserCircle, X, Compass,
  Activity, ChevronRight
} from 'lucide-react';

const NAV_SECTIONS = [
  {
    label: 'ОГЛЯД',
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Дашборд', end: true },
      { to: '/sports-hub', icon: Compass, label: 'Sport Hub' },
    ],
  },
  {
    label: 'ДАНІ',
    items: [
      { to: '/matches', icon: CalendarDays, label: 'Матчі' },
      { to: '/teams', icon: Users, label: 'Команди' },
      { to: '/standings', icon: TableProperties, label: 'Таблиця' },
    ],
  },
  {
    label: 'AI АНАЛІТИКА',
    items: [
      { to: '/predictions', icon: Zap, label: 'Прогнози', accent: '#F59E0B' },
      { to: '/ai-models', icon: Brain, label: 'AI Моделі', accent: '#8B5CF6' },
      { to: '/profile', icon: UserCircle, label: 'Мій профіль' },
    ],
  },
];

function PulseDot({ color = '#10B981' }) {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      <span className="absolute inline-flex h-full w-full rounded-full animate-ping opacity-60" style={{ background: color }} />
      <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: color }} />
    </span>
  );
}

function MiniAccuracyCard({ stats }) {
  const acc = stats?.accuracy_percent ?? null;
  const total = stats?.total_predictions ?? 0;
  const correct = stats?.correct_predictions ?? 0;

  return (
    <div className="mx-3 mb-3 rounded-xl p-3" style={{ background: 'rgba(59,130,246,0.07)', border: '1px solid rgba(59,130,246,0.15)' }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5" style={{ color: '#3B82F6' }} />
          <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: '#3B82F6' }}>AI Engine</span>
        </div>
        <PulseDot />
      </div>
      {acc !== null ? (
        <>
          <div className="flex items-end gap-1 mb-1.5">
            <span className="text-2xl font-black text-white">{acc.toFixed(1)}</span>
            <span className="text-sm font-bold mb-0.5" style={{ color: '#3B82F6' }}>%</span>
            <span className="text-[10px] ml-auto" style={{ color: '#5a7a9a' }}>точність</span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(148,200,255,0.1)' }}>
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{ width: `${Math.min(acc, 100)}%`, background: 'linear-gradient(90deg,#3B82F6,#10B981)' }}
            />
          </div>
          <div className="flex justify-between mt-1.5 text-[10px]" style={{ color: '#3d6080' }}>
            <span>{correct} вірних</span>
            <span>{total} всього</span>
          </div>
        </>
      ) : (
        <div className="flex items-center gap-2 mt-1">
          <div
            className="w-4 h-4 rounded-full animate-spin"
            style={{ border: '2px solid rgba(59,130,246,0.2)', borderTopColor: '#3B82F6' }}
          />
          <p className="text-[11px]" style={{ color: '#3d6080' }}>Завантаження...</p>
        </div>
      )}
    </div>
  );
}

export default function Sidebar({ open = false, onClose = () => {} }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sysStats, setSysStats] = useState(null);

  useEffect(() => {
    api.get('/dashboard/stats').then(r => setSysStats(r.data)).catch(() => {});
  }, []);

  const handleLogout = () => {
    logout();
    onClose();
    navigate('/login');
  };

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed left-0 top-0 z-50 flex h-screen w-64 flex-col transition-transform duration-300 md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
        style={{ background: '#040D1C', borderRight: '1px solid rgba(148,200,255,0.07)' }}
      >
        {/* Logo */}
        <div className="px-4 pt-5 pb-4" style={{ borderBottom: '1px solid rgba(148,200,255,0.06)' }}>
          <div className="flex items-center justify-end mb-3 md:hidden">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-white/10 p-1 text-slate-400 hover:text-white transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center gap-3">
            <div
              className="flex h-9 w-9 items-center justify-center rounded-xl shrink-0 relative"
              style={{ background: 'linear-gradient(135deg, #1D4ED8 0%, #0891B2 100%)', boxShadow: '0 0 18px rgba(29,78,216,0.45)' }}
            >
              <Trophy className="h-4 w-4 text-white" />
              <span
                className="absolute -top-0.5 -right-0.5 flex h-3 w-3 items-center justify-center rounded-full text-[7px] font-black text-white"
                style={{ background: '#10B981', boxShadow: '0 0 8px rgba(16,185,129,0.8)' }}
              >
                AI
              </span>
            </div>
            <div>
              <h1 className="text-[15px] font-black tracking-wide text-white">SportPredict</h1>
              <div className="flex items-center gap-1.5 mt-0.5">
                <PulseDot />
                <p className="text-[10px] font-semibold" style={{ color: '#10B981' }}>Система активна</p>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2 px-2">
          {NAV_SECTIONS.map((section, si) => (
            <div key={si} className={si > 0 ? 'mt-3' : ''}>
              <p
                className="px-3 py-1 text-[9px] font-black tracking-[0.15em] select-none"
                style={{ color: '#2a4060' }}
              >
                {section.label}
              </p>
              {section.items.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `group relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 my-0.5 ${isActive ? 'nav-active text-white' : 'hover:bg-white/[0.04]'}`
                  }
                  style={({ isActive }) => isActive ? {} : { color: '#4a6a8a' }}
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span
                          className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full"
                          style={{ background: item.accent || '#3B82F6' }}
                        />
                      )}
                      <item.icon
                        className="w-4 h-4 shrink-0 transition-colors"
                        style={{ color: isActive ? '#fff' : (item.accent || '#4a6a8a') }}
                      />
                      <span className="flex-1">{item.label}</span>
                      {isActive && <ChevronRight className="w-3 h-3 opacity-40" />}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* AI Stats card */}
        <MiniAccuracyCard stats={sysStats} />

        {/* User footer */}
        <div className="p-3" style={{ borderTop: '1px solid rgba(148,200,255,0.06)' }}>
          <div
            className="flex items-center gap-3 rounded-xl px-3 py-2.5"
            style={{ background: 'rgba(148,200,255,0.03)', border: '1px solid rgba(148,200,255,0.07)' }}
          >
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-black text-white"
              style={{ background: 'linear-gradient(135deg, #1D4ED8 0%, #10B981 100%)' }}
            >
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white truncate">{user?.username}</p>
              <span
                className="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider mt-0.5"
                style={{
                  background: user?.role === 'admin' ? 'rgba(139,92,246,0.2)' : 'rgba(59,130,246,0.15)',
                  color: user?.role === 'admin' ? '#A78BFA' : '#60A5FA',
                  border: user?.role === 'admin' ? '1px solid rgba(139,92,246,0.3)' : '1px solid rgba(59,130,246,0.2)',
                }}
              >
                {user?.role || 'user'}
              </span>
            </div>
            <button
              onClick={handleLogout}
              className="transition-colors hover:text-red-400"
              style={{ color: '#3d6080' }}
              aria-label="Вийти"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
