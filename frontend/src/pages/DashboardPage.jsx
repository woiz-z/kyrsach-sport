import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { formatUkrDate, formatUkrDateTime } from '../utils/date';
import {
  BarChart3, Trophy, CalendarDays, Zap, Target, Users, TrendingUp, Activity
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend
} from 'recharts';
import SportBadge from '../components/SportBadge';
import { useSportMode } from '../context/SportModeContext';

const STAT_CARDS = [
  { label: 'Всього матчів',   key: 'total_matches',      icon: CalendarDays },
  { label: 'Завершено',       key: 'completed_matches',  icon: Trophy       },
  { label: 'Заплановано',     key: 'upcoming_matches',   icon: Activity     },
  { label: 'Всього прогнозів',key: 'total_predictions',  icon: Zap          },
  { label: 'Вірних прогнозів',key: 'correct_predictions',icon: Target       },
  { label: 'Точність AI',     key: 'accuracy_percent',   icon: TrendingUp,  suffix: '%' },
  { label: 'Команд',          key: 'total_teams',        icon: Users        },
  { label: 'Видів спорту',    key: 'total_sports',       icon: BarChart3    },
];

export default function DashboardPage() {
  const { activeSportId, theme, activeSport } = useSportMode();
  const [stats, setStats] = useState(null);
  const [upcoming, setUpcoming] = useState([]);
  const [recentPreds, setRecentPreds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    setLoading(true);
    const sportParam = activeSportId ? { sport_id: activeSportId } : {};
    Promise.allSettled([
      api.get('/dashboard/stats', { params: sportParam }),
      api.get('/matches/upcoming', { params: { limit: 5, ...sportParam } }),
      api.get('/predictions/', { params: { limit: 5, ...sportParam } }),
    ]).then(([s, u, p]) => {
      if (s.status === 'fulfilled') setStats(s.value.data);
      if (u.status === 'fulfilled') setUpcoming(u.value.data);
      if (p.status === 'fulfilled') setRecentPreds(p.value.data);
      if ([s, u, p].every(r => r.status === 'rejected'))
        setError('Не вдалося завантажити дані дашборду.');
    }).finally(() => setLoading(false));
  }, [activeSportId, activeSport]);

  if (loading) return <LoadingSpinner accentColor={theme.accent} />;

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
  const PIE_COLORS = [theme.accent2, theme.accent];

  return (
    <div className="space-y-8 animate-float-up">
      <div>
        <h1 className="text-5xl font-normal tracking-wider text-white uppercase" style={{ fontFamily: 'var(--font-stat)' }}>
          Дашборд
        </h1>
        <p className="mt-1 text-xs font-medium uppercase tracking-widest" style={{ color: '#4a6a8a' }}>
          Огляд системи прогнозування SportPredict AI
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {STAT_CARDS.map((card) => {
          const rawVal = stats?.[card.key] ?? 0;
          const value = card.suffix ? `${rawVal}${card.suffix}` : rawVal;
          return (
            <div key={card.key} className="stat-card p-5 flex flex-col gap-2 overflow-hidden relative">
              {/* accent top border line */}
              <div className="absolute top-0 left-0 right-0 h-[2px] rounded-t-2xl opacity-60"
                style={{ background: theme.gradient }} />
              <div className="flex items-center justify-between">
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: `${theme.accent}15` }}
                >
                  <card.icon className="w-4 h-4" style={{ color: theme.accent }} />
                </div>
                <span className="text-[9px] font-bold tracking-widest uppercase px-2 py-0.5 rounded-full"
                  style={{ background: `${theme.accent}18`, color: theme.accent }}>
                  live
                </span>
              </div>
              <div className="mt-1">
                <p className="stat-number text-5xl font-normal text-white leading-none"
                  style={{ textShadow: `0 0 30px ${theme.glow}` }}>
                  {value}
                </p>
                <p className="text-[11px] font-medium mt-2 uppercase tracking-wider" style={{ color: '#4a6a8a' }}>
                  {card.label}
                </p>
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
            <Link to="/matches" className="text-xs font-semibold transition-colors" style={{ color: theme.accent2 }}>
              Всі матчі →
            </Link>
          </div>
          <div className="space-y-2">
            {upcoming.length === 0 ? (
              <p className="text-center py-8 text-sm" style={{ color: '#5a7a9a' }}>Немає запланованих матчів</p>
            ) : upcoming.map(m => (
              <Link key={m.id} to={`/matches/${m.id}`}
                className="flex items-center gap-3 p-3 rounded-xl transition-all"
                style={{ border: '1px solid rgba(255,255,255,0.04)' }}
              >
                <div className="text-right flex-1 min-w-0">
                  <span className="font-semibold text-sm text-white truncate block">{m.home_team?.name}</span>
                </div>
                <div className="px-2 py-1 rounded-lg text-xs font-bold shrink-0" style={{ background: `${theme.accent}18`, color: theme.accent2 }}>
                  VS
                </div>
                <div className="flex-1 min-w-0">
                  <span className="font-semibold text-sm text-white truncate block">{m.away_team?.name}</span>
                </div>
                <SportBadge sportName={m.sport?.name} icon={m.sport?.icon} />
                <span className="text-xs shrink-0" style={{ color: '#5a7a9a' }}>
                  {formatUkrDate(m.match_date)}
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
          <Link to="/predictions" className="text-xs font-semibold transition-colors" style={{ color: theme.accent2 }}>
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
                    <Link to={`/matches/${p.match_id}`} className="font-medium transition-colors" style={{ color: theme.accent2 }}>
                      {p.match?.home_team?.name} vs {p.match?.away_team?.name}
                    </Link>
                  </td>
                  <td className="py-3"><ResultBadge result={p.predicted_result} /></td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(148,200,255,0.1)' }}>
                        <div className="h-full rounded-full" style={{ width: `${(p.confidence || 0) * 100}%`, background: theme.gradient }} />
                      </div>
                      <span className="text-xs" style={{ color: '#5a7a9a' }}>{((p.confidence || 0) * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="py-3 text-xs" style={{ color: '#5a7a9a' }}>
                    {formatUkrDate(p.created_at)}
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

function LoadingSpinner({ accentColor = '#3B82F6' }) {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: `${accentColor}30`, borderTopColor: accentColor }} />
    </div>
  );
}


const COLORS = ['#10b981', '#f59e0b', '#ef4444'];
