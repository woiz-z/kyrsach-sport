import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSportMode } from '../context/SportModeContext';
import { SPORT_THEMES, SPORT_KEYS } from '../constants/sports';
import { useState, useEffect } from 'react';
import api from '../services/api';
import {
  LayoutDashboard, Trophy, Users, Brain, LogOut, Zap,
  CalendarDays, TableProperties, UserCircle, X,
  Activity, ChevronRight, Radio
} from 'lucide-react';

const NAV_SECTIONS = [
  {
    label: 'ОГЛЯД',
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Дашборд', end: true },
    ],
  },
  {
    label: 'ДАНІ',
    items: [
      { to: '/live', icon: Radio, label: 'Live', live: true },
      { to: '/matches', icon: CalendarDays, label: 'Матчі' },
      { to: '/teams', icon: Users, label: 'Команди', tennisHide: true },
      { to: '/players', icon: Activity, label: 'Гравці' },
      { to: '/standings', icon: TableProperties, label: 'Таблиця' },
    ],
  },
  {
    label: 'AI АНАЛІТИКА',
    items: [
      { to: '/predictions', icon: Zap, label: 'Прогнози' },
      { to: '/ai-models', icon: Brain, label: 'AI Моделі', adminOnly: true },
      { to: '/profile', icon: UserCircle, label: 'Мій профіль' },
    ],
  },
];

function PulseDot({ color }) {
  const { theme } = useSportMode();
  const c = color || theme.pulseDot;
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      <span className="absolute inline-flex h-full w-full rounded-full animate-ping opacity-60" style={{ background: c }} />
      <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: c }} />
    </span>
  );
}

function SportModeSwitcher({ onClose }) {
  const { activeSport, theme, switchSport } = useSportMode();

  return (
    <div className="px-3 py-3" style={{ borderBottom: `1px solid ${theme.accent}15` }}>
      <p className="text-[9px] font-black tracking-[0.15em] mb-2 px-1" style={{ color: `${theme.accent}90` }}>
        РЕЖИМ СПОРТУ
      </p>
      <div className="grid grid-cols-3 gap-1.5">
        {SPORT_KEYS.map(key => {
          const t = SPORT_THEMES[key];
          const isActive = activeSport === key;
          return (
            <button
              key={key}
              onClick={() => { switchSport(key); onClose(); }}
              title={t.name}
              className="flex flex-col items-center gap-1 rounded-xl py-2 px-1 transition-all duration-200"
              style={isActive
                ? {
                    background: t.gradient,
                    boxShadow: `0 4px 14px ${t.glow}`,
                    border: `1px solid ${t.accent2}50`,
                  }
                : {
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.09)',
                  }
              }
            >
              <span className="text-lg leading-none">{t.icon}</span>
              <span
                className="text-[8px] font-bold leading-none text-center"
                style={{ color: isActive ? '#fff' : '#4a6a8a', letterSpacing: '0.02em' }}
              >
                {t.name.split(' ')[0]}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MiniAccuracyCard({ stats }) {
  const { theme } = useSportMode();
  const acc = stats?.accuracy_percent ?? null;
  const resolved = stats?.resolved_predictions ?? stats?.total_predictions ?? 0;
  const correct = stats?.correct_predictions ?? 0;

  return (
    <div className="mx-3 mb-3 rounded-xl p-3" style={{ background: `${theme.accent}10`, border: `1px solid ${theme.accent}22` }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5" style={{ color: theme.accent }} />
          <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: theme.accent }}>AI Engine</span>
        </div>
        <PulseDot />
      </div>
      {acc !== null ? (
        <>
          <div className="flex items-end gap-1 mb-1.5">
            <span className="stat-number text-4xl text-white" style={{ textShadow: `0 0 20px ${theme.glow}` }}>
              {acc.toFixed(1)}
            </span>
            <span className="text-base font-bold mb-1" style={{ color: theme.accent }}>%</span>
            <span className="text-[9px] ml-auto font-semibold uppercase tracking-wider" style={{ color: '#5a7a9a' }}>точність</span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: `${theme.accent}18` }}>
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{ width: `${Math.min(acc, 100)}%`, background: theme.gradient }}
            />
          </div>
          <div className="flex justify-between mt-1.5 text-[10px]" style={{ color: '#3d6080' }}>
            <span>{correct} вірних</span>
            <span>{resolved} вирішених</span>
          </div>
        </>
      ) : (
        <div className="flex items-center gap-2 mt-1">
          <div
            className="w-4 h-4 rounded-full animate-spin"
            style={{ border: `2px solid ${theme.accent}30`, borderTopColor: theme.accent }}
          />
          <p className="text-[11px]" style={{ color: '#3d6080' }}>Завантаження...</p>
        </div>
      )}
    </div>
  );
}

export default function Sidebar({ open = false, onClose = () => {} }) {
  const { user, logout } = useAuth();
  const { theme, activeSport } = useSportMode();
  const navigate = useNavigate();
  const [sysStats, setSysStats] = useState(null);

  useEffect(() => {
    api.get('/dashboard/stats').then(r => setSysStats(r.data)).catch(() => {});
  }, [activeSport]);

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
        className={`fixed left-0 top-0 z-50 flex h-screen w-64 flex-col transition-all duration-300 md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
        style={{ background: `${theme.bg}d8`, backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', borderRight: `1px solid ${theme.accent}25` }}
      >
        {/* Logo */}
        <div className="px-4 pt-5 pb-4" style={{ borderBottom: `1px solid ${theme.accent}10` }}>
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
              style={{ background: theme.gradient, boxShadow: `0 0 18px ${theme.glow}` }}
            >
              <Trophy className="h-4 w-4 text-white" />
              <span
                className="absolute -top-0.5 -right-0.5 flex h-3 w-3 items-center justify-center rounded-full text-[7px] font-black text-white"
                style={{ background: theme.accent2, boxShadow: `0 0 8px ${theme.glow}` }}
              >
                AI
              </span>
            </div>
            <div className="min-w-0">
              <h1 className="brand-gradient-text text-[17px] font-black tracking-widest uppercase"
                style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.08em' }}>
                SportPredict
              </h1>
              <div className="flex items-center gap-1.5 mt-0.5">
                <PulseDot />
                <p className="text-[9px] font-bold uppercase tracking-widest" style={{ color: theme.pulseDot }}>
                  {SPORT_THEMES[activeSport]?.name}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Sport Mode Switcher */}
        <SportModeSwitcher onClose={onClose} />

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
              {section.items.filter(item => (!item.adminOnly || user?.role === 'admin') && (!item.tennisHide || activeSport !== 'tennis')).map(item => (
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
                          style={{ background: theme.accent2 }}
                        />
                      )}
                      <item.icon
                        className="w-4 h-4 shrink-0 transition-colors"
                        style={{ color: isActive ? '#fff' : item.live ? '#ef4444' : '#4a6a8a' }}
                      />
                      <span className="flex-1">{item.label}</span>
                      {item.live && !isActive && (
                        <span className="relative flex h-2 w-2 shrink-0">
                          <span className="absolute inline-flex h-full w-full rounded-full animate-ping opacity-70" style={{ background: '#ef4444' }} />
                          <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: '#ef4444' }} />
                        </span>
                      )}
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
        <div className="p-3" style={{ borderTop: `1px solid ${theme.accent}10` }}>
          <div
            className="flex items-center gap-3 rounded-xl px-3 py-2.5"
            style={{ background: `${theme.accent}06`, border: `1px solid ${theme.accent}12` }}
          >
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-black text-white"
              style={{ background: theme.gradient }}
            >
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white truncate">{user?.username}</p>
              <span
                className="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider mt-0.5"
                style={{
                  background: user?.role === 'admin' ? 'rgba(139,92,246,0.2)' : `${theme.accent}20`,
                  color: user?.role === 'admin' ? '#A78BFA' : theme.accent2,
                  border: user?.role === 'admin' ? '1px solid rgba(139,92,246,0.3)' : `1px solid ${theme.accent}30`,
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
