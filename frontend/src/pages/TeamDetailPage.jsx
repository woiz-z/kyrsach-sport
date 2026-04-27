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
      <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(59,130,246,0.2)', borderTopColor: '#3B82F6' }} />
    </div>
  );

  if (error) return <div className="text-center py-20" style={{ color: '#EF4444' }}>{error}</div>;

  if (!team) return <div className="text-center py-20" style={{ color: '#5a7a9a' }}>Команду не знайдено</div>;

  const latestStats = stats[0];

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Link to="/teams" className="inline-flex items-center gap-2 text-sm transition-colors" style={{ color: '#5a7a9a' }}>
        <ArrowLeft className="w-4 h-4" /> Назад до команд
      </Link>

      {/* Team Header */}
      <div className="rounded-2xl p-8 text-white" style={{ background: 'linear-gradient(135deg,#0D1B2E,#1D4ED8,#0891B2)' }}>
        <div className="flex items-center gap-6">
          <div className="w-24 h-24 rounded-2xl flex items-center justify-center text-5xl font-bold" style={{ background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(12px)' }}>
            {team.name.charAt(0)}
          </div>
          <div>
            <h1 className="text-3xl font-bold">{team.name}</h1>
            <div className="flex items-center gap-4 mt-2" style={{ color: 'rgba(147,197,253,0.8)' }}>
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

      {stats.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-6 py-4" style={{ borderBottom: '1px solid rgba(148,200,255,0.08)' }}>
            <h3 className="font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5" style={{ color: '#3B82F6' }} /> Статистика по сезонах
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left" style={{ background: 'rgba(148,200,255,0.04)', color: '#5a7a9a', borderBottom: '1px solid rgba(148,200,255,0.08)' }}>
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
              <tbody>
                {stats.map((s, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(148,200,255,0.06)' }}>
                    <td className="px-6 py-3 font-medium text-white">Сезон #{s.season_id}</td>
                    <td className="px-4 py-3 text-center" style={{ color: '#E2EEFF' }}>{s.matches_played}</td>
                    <td className="px-4 py-3 text-center font-medium" style={{ color: '#10B981' }}>{s.wins}</td>
                    <td className="px-4 py-3 text-center" style={{ color: '#F59E0B' }}>{s.draws}</td>
                    <td className="px-4 py-3 text-center" style={{ color: '#EF4444' }}>{s.losses}</td>
                    <td className="px-4 py-3 text-center" style={{ color: '#E2EEFF' }}>{s.goals_for}</td>
                    <td className="px-4 py-3 text-center" style={{ color: '#5a7a9a' }}>{s.goals_against}</td>
                    <td className="px-4 py-3 text-center font-bold" style={{ color: '#3B82F6' }}>{s.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {players.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-6 py-4" style={{ borderBottom: '1px solid rgba(148,200,255,0.08)' }}>
            <h3 className="font-bold text-white flex items-center gap-2">
              <Users className="w-5 h-5" style={{ color: '#3B82F6' }} /> Гравці ({players.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2">
            {players.map(p => (
              <div key={p.id} className="flex items-center gap-3 px-6 py-3" style={{ borderBottom: '1px solid rgba(148,200,255,0.05)' }}>
                <div className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold" style={{ background: 'linear-gradient(135deg,#1D4ED8,#0891B2)' }}>
                  {p.name?.charAt(0)?.toUpperCase() ?? '?'}
                </div>
                <div>
                  <p className="font-medium text-sm text-white">{p.name}</p>
                  <p className="text-xs" style={{ color: '#5a7a9a' }}>{p.position}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const STAT_COLORS = {
  blue:    { text: '#3B82F6', bg: 'rgba(59,130,246,0.1)'   },
  emerald: { text: '#10B981', bg: 'rgba(16,185,129,0.1)'   },
  amber:   { text: '#F59E0B', bg: 'rgba(245,158,11,0.1)'   },
  red:     { text: '#EF4444', bg: 'rgba(239,68,68,0.1)'    },
  slate:   { text: '#5a7a9a', bg: 'rgba(148,200,255,0.06)' },
};

function StatCard({ label, value, icon: Icon, color = 'blue' }) {
  const c = STAT_COLORS[color] ?? STAT_COLORS.blue;
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs" style={{ color: '#5a7a9a' }}>{label}</p>
        {Icon && (
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: c.bg }}>
            <Icon className="w-4 h-4" style={{ color: c.text }} />
          </div>
        )}
      </div>
      <p className="text-2xl font-bold" style={{ color: c.text }}>{value}</p>
    </div>
  );
}
