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
      {open && <div className="fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-sm md:hidden" onClick={onClose} />}
      <aside className={`fixed left-0 top-0 z-50 flex h-screen w-64 flex-col bg-[#0b1329] text-white transition-transform duration-300 md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
      {/* Logo */}
      <div className="border-b border-white/10 p-6">
        <div className="mb-4 flex items-center justify-end md:hidden">
          <button type="button" onClick={onClose} className="rounded-lg border border-white/20 p-1 text-slate-300">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-lime-400">
            <Trophy className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-black tracking-wide">SportPredict</h1>
            <p className="text-xs text-slate-400">AI Прогнози Multi-Sport</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400 to-lime-400 text-sm font-bold text-slate-950">
            {user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.username}</p>
            <p className="text-xs text-slate-400 capitalize">{user?.role}</p>
          </div>
          <button onClick={handleLogout} className="text-slate-400 hover:text-red-400 transition-colors" aria-label="Вийти">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
      </aside>
    </>
  );
}
