import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import {
  BarChart3, Trophy, CalendarDays, Zap, Target, Users, TrendingUp, Activity
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend
} from 'recharts';
import SportBadge from '../components/SportBadge';

const STAT_CARDS = [
  { label: 'Всього матчів',   key: 'total_matches',     icon: CalendarDays, color: '#3B82F6', glow: 'rgba(59,130,246,0.35)' },
  { label: 'Завершено',       key: 'completed_matches', icon: Trophy,       color: '#10B981', glow: 'rgba(16,185,129,0.35)' },
  { label: 'Заплановано',     key: 'upcoming_matches',  icon: Activity,     color: '#F59E0B', glow: 'rgba(245,158,11,0.35)' },
  { label: 'Всього прогнозів',key: 'total_predictions', icon: Zap,          color: '#8B5CF6', glow: 'rgba(139,92,246,0.35)' },
  { label: 'Вірних прогнозів',key: 'correct_predictions',icon: Target,      color: '#10B981', glow: 'rgba(16,185,129,0.35)' },
  { label: 'Точність AI',     key: 'accuracy_percent',  icon: TrendingUp,   color: '#06B6D4', glow: 'rgba(6,182,212,0.35)', suffix: '%' },
  { label: 'Команд',          key: 'total_teams',       icon: Users,        color: '#EC4899', glow: 'rgba(236,72,153,0.35)' },
  { label: 'Видів спорту',    key: 'total_sports',      icon: BarChart3,    color: '#F59E0B', glow: 'rgba(245,158,11,0.35)' },
];

const PIE_COLORS = ['#10B981', '#3B82F6'];

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [upcoming, setUpcoming] = useState([]);
  const [recentPreds, setRecentPreds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    Promise.allSettled([
      api.get('/dashboard/stats'),
      api.get('/matches/upcoming?limit=5'),
      api.get('/predictions/?limit=5'),
    ]).then(([s, u, p]) => {
      if (s.status === 'fulfilled') setStats(s.value.data);
      if (u.status === 'fulfilled') setUpcoming(u.value.data);
      if (p.status === 'fulfilled') setRecentPreds(p.value.data);
      if ([s, u, p].every(r => r.status === 'rejected'))
        setError('Не вдалося завантажити дані дашборду.');
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  if (error) return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold text-white">Дашборд</h1>
      <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>
    </div>
  );

  const pieData = stats ? [
    { name: 'Завершено', value: stats.completed_matches },
    { name: 'Заплановано', value: stats.upcoming_matches },
  ] : [];

  return (
    <div className="space-y-8 animate-float-up">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">Дашборд</h1>
        <p className="mt-1 text-sm" style={{ color: '#5a7a9a' }}>Огляд системи прогнозування SportPredict AI</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {STAT_CARDS.map((card) => {
          const rawVal = stats?.[card.key] ?? 0;
          const value = card.suffix ? `${rawVal}${card.suffix}` : rawVal;
          return (
            <div key={card.key} className="stat-card p-5 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: `${card.color}18`, boxShadow: `0 0 16px ${card.glow}` }}
                >
                  <card.icon className="w-5 h-5" style={{ color: card.color }} />
                </div>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ background: `${card.color}18`, color: card.color }}>
                  live
                </span>
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{value}</p>
                <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>{card.label}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upcoming Matches */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-bold text-white">Найближчі матчі</h2>
            <Link to="/matches" className="text-xs font-semibold hover:text-blue-300 transition-colors" style={{ color: '#3B82F6' }}>
              Всі матчі →
            </Link>
          </div>
          <div className="space-y-2">
            {upcoming.length === 0 ? (
              <p className="text-center py-8 text-sm" style={{ color: '#5a7a9a' }}>Немає запланованих матчів</p>
            ) : upcoming.map(m => (
              <Link key={m.id} to={`/matches/${m.id}`}
                className="flex items-center gap-3 p-3 rounded-xl border border-white/[0.04] hover:border-blue-500/20 hover:bg-blue-500/[0.05] transition-all"
              >
                <div className="text-right flex-1 min-w-0">
                  <span className="font-semibold text-sm text-white truncate block">{m.home_team?.name}</span>
                </div>
                <div className="px-2 py-1 rounded-lg text-xs font-bold shrink-0" style={{ background: 'rgba(59,130,246,0.15)', color: '#60a5fa' }}>
                  VS
                </div>
                <div className="flex-1 min-w-0">
                  <span className="font-semibold text-sm text-white truncate block">{m.away_team?.name}</span>
                </div>
                <SportBadge sportName={m.sport?.name} icon={m.sport?.icon} />
                <span className="text-xs shrink-0" style={{ color: '#5a7a9a' }}>
                  {new Date(m.match_date).toLocaleDateString('uk-UA')}
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* Pie chart */}
        <div className="glass-card p-6">
          <h2 className="text-base font-bold text-white mb-5">Статус матчів</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i]} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0D1B2E', border: '1px solid rgba(148,200,255,0.1)', borderRadius: 10, color: '#E2EEFF' }}
                />
                <Legend
                  formatter={(value) => <span style={{ color: '#E2EEFF', fontSize: 12 }}>{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Predictions */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold text-white">Останні прогнози</h2>
          <Link to="/predictions" className="text-xs font-semibold hover:text-blue-300 transition-colors" style={{ color: '#3B82F6' }}>
            Всі прогнози →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider" style={{ color: '#5a7a9a', borderBottom: '1px solid rgba(148,200,255,0.06)' }}>
                <th className="pb-3 font-medium">Матч</th>
                <th className="pb-3 font-medium">Прогноз</th>
                <th className="pb-3 font-medium">Впевненість</th>
                <th className="pb-3 font-medium">Дата</th>
              </tr>
            </thead>
            <tbody>
              {recentPreds.map(p => (
                <tr key={p.id} className="dark-row" style={{ borderBottom: '1px solid rgba(148,200,255,0.04)' }}>
                  <td className="py-3">
                    <Link to={`/matches/${p.match_id}`} className="font-medium text-blue-400 hover:text-blue-300 transition-colors">
                      {p.match?.home_team?.name} vs {p.match?.away_team?.name}
                    </Link>
                  </td>
                  <td className="py-3"><ResultBadge result={p.predicted_result} /></td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(148,200,255,0.1)' }}>
                        <div className="h-full rounded-full" style={{ width: `${(p.confidence || 0) * 100}%`, background: 'linear-gradient(90deg, #3B82F6, #06B6D4)' }} />
                      </div>
                      <span className="text-xs" style={{ color: '#5a7a9a' }}>{((p.confidence || 0) * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="py-3 text-xs" style={{ color: '#5a7a9a' }}>
                    {new Date(p.created_at).toLocaleDateString('uk-UA')}
                  </td>
                </tr>
              ))}
              {recentPreds.length === 0 && (
                <tr><td colSpan={4} className="py-8 text-center text-sm" style={{ color: '#5a7a9a' }}>Ще немає прогнозів</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ResultBadge({ result }) {
  const config = {
    home_win: { label: 'П1', color: '#10B981', bg: 'rgba(16,185,129,0.15)' },
    away_win: { label: 'П2', color: '#EF4444', bg: 'rgba(239,68,68,0.15)' },
    draw:     { label: 'Нічия', color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' },
  };
  const c = config[result] || config.draw;
  return (
    <span className="px-2.5 py-1 rounded-lg text-xs font-bold" style={{ background: c.bg, color: c.color }}>
      {c.label}
    </span>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(59,130,246,0.2)', borderTopColor: '#3B82F6' }} />
    </div>
  );
}


const COLORS = ['#10b981', '#f59e0b', '#ef4444'];
