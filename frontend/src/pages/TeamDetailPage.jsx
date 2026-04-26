import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../services/api';
import { ArrowLeft, MapPin, Trophy, Users, TrendingUp, Calendar } from 'lucide-react';

export default function TeamDetailPage() {
  const { id } = useParams();
  const [team, setTeam] = useState(null);
  const [stats, setStats] = useState([]);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    setLoading(true);
    Promise.all([
      api.get(`/teams/${id}`),
      api.get(`/teams/${id}/statistics`),
      api.get(`/teams/${id}/players`),
    ]).then(([t, s, p]) => {
      setTeam(t.data);
      setStats(s.data);
      setPlayers(p.data);
    }).catch((err) => {
      console.error(err);
      setError(err.response?.data?.detail || 'Не вдалося завантажити дані команди');
    })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
    </div>
  );

  if (error) return <div className="text-center py-20 text-red-500">{error}</div>;

  if (!team) return <div className="text-center py-20 text-slate-400">Команду не знайдено</div>;

  const latestStats = stats[0];

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Link to="/teams" className="inline-flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors text-sm">
        <ArrowLeft className="w-4 h-4" /> Назад до команд
      </Link>

      {/* Team Header */}
      <div className="bg-gradient-to-r from-blue-600 to-emerald-500 rounded-2xl p-8 text-white">
        <div className="flex items-center gap-6">
          <div className="w-24 h-24 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center text-5xl font-bold">
            {team.name.charAt(0)}
          </div>
          <div>
            <h1 className="text-3xl font-bold">{team.name}</h1>
            <div className="flex items-center gap-4 mt-2 text-blue-100">
              {team.city && <span className="flex items-center gap-1"><MapPin className="w-4 h-4" /> {team.city}</span>}
              {team.founded_year && <span className="flex items-center gap-1"><Trophy className="w-4 h-4" /> Засн. {team.founded_year}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      {latestStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Матчів" value={latestStats.matches_played} icon={Calendar} />
          <StatCard label="Перемог" value={latestStats.wins} icon={Trophy} color="emerald" />
          <StatCard label="Нічиїх" value={latestStats.draws} color="amber" />
          <StatCard label="Поразок" value={latestStats.losses} color="red" />
          <StatCard label="Голів забито" value={latestStats.goals_for} icon={TrendingUp} color="blue" />
          <StatCard label="Голів пропущено" value={latestStats.goals_against} color="slate" />
          <StatCard label="Різниця голів" value={latestStats.goals_for - latestStats.goals_against} color={latestStats.goals_for - latestStats.goals_against >= 0 ? 'emerald' : 'red'} />
          <StatCard label="Очок" value={latestStats.points} icon={Trophy} color="blue" />
        </div>
      )}

      {/* Season Stats Table */}
      {stats.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-500" /> Статистика по сезонах
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50">
                <tr className="text-left text-slate-500">
                  <th className="px-6 py-3 font-medium">Сезон</th>
                  <th className="px-4 py-3 font-medium text-center">М</th>
                  <th className="px-4 py-3 font-medium text-center">В</th>
                  <th className="px-4 py-3 font-medium text-center">Н</th>
                  <th className="px-4 py-3 font-medium text-center">П</th>
                  <th className="px-4 py-3 font-medium text-center">ГЗ</th>
                  <th className="px-4 py-3 font-medium text-center">ГП</th>
                  <th className="px-4 py-3 font-medium text-center">Очки</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {stats.map((s, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-6 py-3 font-medium text-slate-800">Сезон #{s.season_id}</td>
                    <td className="px-4 py-3 text-center">{s.matches_played}</td>
                    <td className="px-4 py-3 text-center text-emerald-600 font-medium">{s.wins}</td>
                    <td className="px-4 py-3 text-center text-amber-600">{s.draws}</td>
                    <td className="px-4 py-3 text-center text-red-600">{s.losses}</td>
                    <td className="px-4 py-3 text-center">{s.goals_for}</td>
                    <td className="px-4 py-3 text-center">{s.goals_against}</td>
                    <td className="px-4 py-3 text-center font-bold text-blue-600">{s.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Players */}
      {players.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <Users className="w-5 h-5 text-blue-500" /> Гравці ({players.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 divide-slate-100">
            {players.map(p => (
              <div key={p.id} className="flex items-center gap-3 px-6 py-3 hover:bg-slate-50">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-sm font-bold">
                  {p.name?.charAt(0)?.toUpperCase() ?? '?'}
                </div>
                <div>
                  <p className="font-medium text-slate-800 text-sm">{p.name}</p>
                  <p className="text-xs text-slate-500">{p.position}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Full class names must be static strings — Tailwind cannot process dynamic interpolation.
const STAT_COLORS = {
  blue:    { text: 'text-blue-600',    bg: 'bg-blue-50',    icon: 'text-blue-500'    },
  emerald: { text: 'text-emerald-600', bg: 'bg-emerald-50', icon: 'text-emerald-500' },
  amber:   { text: 'text-amber-600',   bg: 'bg-amber-50',   icon: 'text-amber-500'   },
  red:     { text: 'text-red-600',     bg: 'bg-red-50',     icon: 'text-red-500'     },
  slate:   { text: 'text-slate-600',   bg: 'bg-slate-50',   icon: 'text-slate-500'   },
};

function StatCard({ label, value, icon: Icon, color = 'blue' }) {
  const c = STAT_COLORS[color] ?? STAT_COLORS.blue;
  return (
    <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-100">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-slate-500">{label}</p>
        {Icon && (
          <div className={`w-7 h-7 rounded-lg ${c.bg} flex items-center justify-center`}>
            <Icon className={`w-4 h-4 ${c.icon}`} />
          </div>
        )}
      </div>
      <p className={`text-2xl font-bold ${c.text}`}>{value}</p>
    </div>
  );
}
