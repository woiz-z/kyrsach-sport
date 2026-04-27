import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard, Trophy, Users, BarChart3, Brain, LogOut, Zap, CalendarDays, TableProperties, UserCircle, X, Compass
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Дашборд' },
  { to: '/sports-hub', icon: Compass, label: 'Sport Hub' },
  { to: '/matches', icon: CalendarDays, label: 'Матчі' },
  { to: '/teams', icon: Users, label: 'Команди' },
  { to: '/standings', icon: TableProperties, label: 'Таблиця' },
  { to: '/predictions', icon: Zap, label: 'Прогнози' },
  { to: '/ai-models', icon: Brain, label: 'AI Моделі' },
  { to: '/profile', icon: UserCircle, label: 'Мій профіль' },
];

export default function Sidebar({ open = false, onClose = () => {} }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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
        className={`fixed left-0 top-0 z-50 flex h-screen w-64 flex-col transition-transform duration-300 md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
        style={{ background: '#040D1C', borderRight: '1px solid rgba(148,200,255,0.07)' }}
      >
        {/* Logo */}
        <div className="p-6" style={{ borderBottom: '1px solid rgba(148,200,255,0.07)' }}>
          <div className="mb-4 flex items-center justify-end md:hidden">
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
              className="flex h-10 w-10 items-center justify-center rounded-xl shrink-0"
              style={{ background: 'linear-gradient(135deg, #3B82F6 0%, #06B6D4 100%)', boxShadow: '0 0 20px rgba(59,130,246,0.4)' }}
            >
              <Trophy className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-black tracking-wider text-white">SportPredict</h1>
              <p className="text-[11px]" style={{ color: '#3d6080' }}>AI Прогнози Multi-Sport</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-0.5 p-3 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'nav-active'
                    : 'text-[#5a7a9a] hover:text-white hover:bg-white/[0.05]'
                }`
              }
            >
              <item.icon className="w-4.5 h-4.5 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div className="p-3" style={{ borderTop: '1px solid rgba(148,200,255,0.07)' }}>
          <div className="flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-white/[0.04] transition-colors group">
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #3B82F6 0%, #10B981 100%)' }}
            >
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white truncate">{user?.username}</p>
              <p className="text-[11px] capitalize" style={{ color: '#3d6080' }}>{user?.role}</p>
            </div>
            <button
              onClick={handleLogout}
              className="text-[#3d6080] hover:text-red-400 transition-colors ml-auto"
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

