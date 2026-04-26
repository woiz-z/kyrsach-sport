import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import {
  BarChart3, Trophy, CalendarDays, Zap, Target, Users, TrendingUp, Activity
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line
} from 'recharts';
import SportBadge from '../components/SportBadge';

const COLORS = ['#10b981', '#f59e0b', '#ef4444'];

// Tailwind does not support dynamic class interpolation (e.g. `bg-${color}-50`).
// All class names must appear as full strings in source to be included in the build.
const CARD_COLORS = {
  blue:    { bg: 'bg-blue-50',    icon: 'text-blue-500'    },
  emerald: { bg: 'bg-emerald-50', icon: 'text-emerald-500' },
  amber:   { bg: 'bg-amber-50',   icon: 'text-amber-500'   },
  purple:  { bg: 'bg-purple-50',  icon: 'text-purple-500'  },
  green:   { bg: 'bg-green-50',   icon: 'text-green-500'   },
  indigo:  { bg: 'bg-indigo-50',  icon: 'text-indigo-500'  },
  pink:    { bg: 'bg-pink-50',    icon: 'text-pink-500'    },
};

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
      const failed = [s, u, p].filter(r => r.status === 'rejected');
      if (failed.length === 3) {
        setError('Не вдалося завантажити дані дашборду. Спробуйте оновити сторінку.');
      }
    })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-3xl font-bold text-slate-800">Дашборд</h1>
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  const statCards = [
    { label: 'Всього матчів', value: stats?.total_matches || 0, icon: CalendarDays, color: 'blue' },
    { label: 'Завершено', value: stats?.completed_matches || 0, icon: Trophy, color: 'emerald' },
    { label: 'Заплановано', value: stats?.upcoming_matches || 0, icon: Activity, color: 'amber' },
    { label: 'Всього прогнозів', value: stats?.total_predictions || 0, icon: Zap, color: 'purple' },
    { label: 'Вірних прогнозів', value: stats?.correct_predictions || 0, icon: Target, color: 'green' },
    { label: 'Точність AI', value: `${stats?.accuracy_percent || 0}%`, icon: TrendingUp, color: 'blue' },
    { label: 'Команд', value: stats?.total_teams || 0, icon: Users, color: 'indigo' },
    { label: 'Видів спорту', value: stats?.total_sports || 0, icon: BarChart3, color: 'pink' },
  ];

  const pieData = stats ? [
    { name: 'Завершено', value: stats.completed_matches },
    { name: 'Заплановано', value: stats.upcoming_matches },
  ] : [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-800">Дашборд</h1>
        <p className="text-slate-500 mt-1">Огляд системи прогнозування SportPredict AI</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, i) => (
          <div key={i} className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">{card.label}</p>
                <p className="text-2xl font-bold mt-1">{card.value}</p>
              </div>
              <div className={`w-12 h-12 rounded-xl ${CARD_COLORS[card.color]?.bg ?? 'bg-slate-50'} flex items-center justify-center`}>
                <card.icon className={`w-6 h-6 ${CARD_COLORS[card.color]?.icon ?? 'text-slate-500'}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upcoming Matches */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">Найближчі матчі</h2>
            <Link to="/matches" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              Всі матчі →
            </Link>
          </div>
          <div className="space-y-3">
            {upcoming.length === 0 ? (
              <p className="text-slate-400 text-sm text-center py-8">Немає запланованих матчів</p>
            ) : upcoming.map(m => (
              <Link key={m.id} to={`/matches/${m.id}`}
                className="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 transition-colors border border-slate-100"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="text-right flex-1 truncate">
                    <span className="font-semibold text-sm">{m.home_team?.name}</span>
                  </div>
                  <div className="px-3 py-1 bg-slate-100 rounded-lg text-xs font-bold text-slate-600 shrink-0">
                    VS
                  </div>
                  <div className="flex-1 truncate">
                    <span className="font-semibold text-sm">{m.away_team?.name}</span>
                  </div>
                  <SportBadge sportName={m.sport?.name} icon={m.sport?.icon} />
                </div>
                <span className="text-xs text-slate-400 ml-3 shrink-0">
                  {new Date(m.match_date).toLocaleDateString('uk-UA')}
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* Match Status Pie */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <h2 className="text-lg font-bold mb-4">Статус матчів</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height={256}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={['#10b981', '#f59e0b'][i]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Predictions */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Останні прогнози</h2>
          <Link to="/predictions" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
            Всі прогнози →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-100">
                <th className="pb-3 font-medium">Матч</th>
                <th className="pb-3 font-medium">Прогноз</th>
                <th className="pb-3 font-medium">Впевненість</th>
                <th className="pb-3 font-medium">Дата</th>
              </tr>
            </thead>
            <tbody>
              {recentPreds.map(p => (
                <tr key={p.id} className="border-b border-slate-50">
                  <td className="py-3">
                    <Link to={`/matches/${p.match_id}`} className="font-medium text-blue-600 hover:text-blue-700">
                      {p.match?.home_team?.name} vs {p.match?.away_team?.name}
                    </Link>
                  </td>
                  <td className="py-3">
                    <ResultBadge result={p.predicted_result} />
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(p.confidence || 0) * 100}%` }} />
                      </div>
                      <span className="text-xs text-slate-500">{((p.confidence || 0) * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="py-3 text-slate-400 text-xs">
                    {new Date(p.created_at).toLocaleDateString('uk-UA')}
                  </td>
                </tr>
              ))}
              {recentPreds.length === 0 && (
                <tr><td colSpan={4} className="py-8 text-center text-slate-400">Ще немає прогнозів</td></tr>
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
    home_win: { label: 'Перемога господарів', cls: 'bg-emerald-50 text-emerald-700' },
    away_win: { label: 'Перемога гостей', cls: 'bg-red-50 text-red-700' },
    draw: { label: 'Нічия', cls: 'bg-amber-50 text-amber-700' },
  };
  const c = config[result] || config.draw;
  return <span className={`px-2 py-1 rounded-lg text-xs font-medium ${c.cls}`}>{c.label}</span>;
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
    </div>
  );
}
