import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../services/api';
import { parseAsUTC, formatUkrDate } from '../utils/date';
import PlayerAvatar from '../components/PlayerAvatar';
import { ArrowLeft, Calendar, User, Flag, Ruler, Weight, Hash, Activity, Target, Star } from 'lucide-react';

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = parseAsUTC(dateStr);
  return d.toLocaleDateString('uk-UA', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Kyiv' });
}

function formatScore(home, away) {
  if (home == null || away == null) return '—';
  return `${home}:${away}`;
}

export default function PlayerDetailPage() {
  const { id } = useParams();
  const [player, setPlayer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    setLoading(true);
    api.get(`/players/${id}`)
      .then((res) => setPlayer(res.data))
      .catch((err) => {
        console.error(err);
        setError(err.response?.data?.detail || 'Не вдалося завантажити дані гравця');
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 rounded-full animate-spin"
        style={{ borderColor: 'rgba(59,130,246,0.2)', borderTopColor: '#3B82F6' }} />
    </div>
  );

  if (error) return <div className="text-center py-20" style={{ color: '#EF4444' }}>{error}</div>;
  if (!player) return <div className="text-center py-20" style={{ color: '#5a7a9a' }}>Гравця не знайдено</div>;

  const cs = player.career_stats || {};
  const backLink = '/players';
  const backLabel = '← Гравці';

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Back link */}
      <Link to={backLink} className="inline-flex items-center gap-2 text-sm transition-colors" style={{ color: '#5a7a9a' }}>
        <ArrowLeft className="w-4 h-4" /> {backLabel}
      </Link>

      {/* Header card */}
      <div className="rounded-2xl p-6 text-white" style={{ background: 'linear-gradient(135deg,#0D1B2E,#1D4ED8,#0891B2)' }}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
          {/* Avatar */}
          <div className="flex-shrink-0">
            <PlayerAvatar
              name={player.name}
              photoUrl={player.photo_url}
              playerId={player.id}
              sizeClass="w-24 h-24"
            />
          </div>

          {/* Name + meta */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-3xl font-bold">{player.name}</h1>
              {player.jersey_number != null && (
                <span className="text-xl font-semibold opacity-70">#{player.jersey_number}</span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-4 mt-2" style={{ color: 'rgba(147,197,253,0.85)' }}>
              {player.position && (
                <span className="flex items-center gap-1 text-sm">
                  <User className="w-4 h-4" /> {player.position}
                </span>
              )}
              {player.nationality && (
                <span className="flex items-center gap-1 text-sm">
                  <Flag className="w-4 h-4" /> {player.nationality}
                </span>
              )}
              {player.team && (
                <Link
                  to={`/teams/${player.team.id}`}
                  className="flex items-center gap-1 text-sm hover:text-white transition-colors"
                  style={{ color: 'rgba(147,197,253,0.85)' }}
                >
                  {player.team.logo_url
                    ? <img src={player.team.logo_url} alt="" className="w-5 h-5 rounded object-contain" />
                    : <Star className="w-4 h-4" />}
                  {player.team.name}
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bio row */}
      <div className="glass-card p-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
        <BioItem
          icon={Calendar}
          label="Дата народження"
          value={player.date_of_birth
            ? `${formatDate(player.date_of_birth)}${player.age != null ? ` (${player.age} р.)` : ''}`
            : '—'}
        />
        <BioItem
          icon={Ruler}
          label="Зріст"
          value={player.height_cm ? `${player.height_cm} см` : '—'}
        />
        <BioItem
          icon={Weight}
          label="Вага"
          value={player.weight_kg ? `${player.weight_kg} кг` : '—'}
        />
        <BioItem
          icon={Hash}
          label="Номер"
          value={player.jersey_number != null ? `#${player.jersey_number}` : '—'}
        />
      </div>

      {/* Career stats */}
      <div className="glass-card overflow-hidden">
        <div className="px-6 py-4" style={{ borderBottom: '1px solid rgba(148,200,255,0.08)' }}>
          <h3 className="font-bold text-white flex items-center gap-2">
            <Activity className="w-5 h-5" style={{ color: '#3B82F6' }} /> Кар'єрна статистика
          </h3>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-7 divide-x" style={{ '--tw-divide-opacity': 1, borderColor: 'rgba(148,200,255,0.08)' }}>
          <StatCell label="Ігор" value={cs.appearances ?? 0} />
          <StatCell label="Старт" value={cs.starts ?? 0} />
          <StatCell label="Хв" value={cs.minutes_played ?? 0} />
          <StatCell label="Голи" value={cs.goals ?? 0} color="#3B82F6" />
          <StatCell label="Асисти" value={cs.assists ?? 0} color="#10B981" />
          <StatCell label="ЖК" value={cs.yellow_cards ?? 0} color="#F59E0B" />
          <StatCell label="ЧК" value={cs.red_cards ?? 0} color="#EF4444" />
        </div>
      </div>

      {/* Bio */}
      {player.bio && (
        <div className="glass-card p-6">
          <h3 className="font-bold text-white flex items-center gap-2 mb-3">
            <User className="w-5 h-5" style={{ color: '#3B82F6' }} /> Біографія
          </h3>
          <p className="text-sm leading-relaxed" style={{ color: '#8ab0cc' }}>{player.bio}</p>
        </div>
      )}

      {/* Recent matches */}
      {player.recent_matches && player.recent_matches.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-6 py-4" style={{ borderBottom: '1px solid rgba(148,200,255,0.08)' }}>
            <h3 className="font-bold text-white flex items-center gap-2">
              <Target className="w-5 h-5" style={{ color: '#3B82F6' }} /> Останні матчі
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left" style={{ background: 'rgba(148,200,255,0.04)', color: '#5a7a9a', borderBottom: '1px solid rgba(148,200,255,0.08)' }}>
                  <th className="px-4 py-3 font-medium">Дата</th>
                  <th className="px-4 py-3 font-medium">Матч</th>
                  <th className="px-4 py-3 font-medium text-center">Рах.</th>
                  <th className="px-4 py-3 font-medium text-center">Старт</th>
                  <th className="px-4 py-3 font-medium text-center">Хв</th>
                  <th className="px-4 py-3 font-medium text-center">Г</th>
                  <th className="px-4 py-3 font-medium text-center">А</th>
                </tr>
              </thead>
              <tbody>
                {player.recent_matches.map((m) => (
                  <tr
                    key={m.match_id}
                    className="border-t"
                    style={{ borderColor: 'rgba(148,200,255,0.05)', color: '#c8d9ed' }}
                  >
                    <td className="px-4 py-3 text-xs whitespace-nowrap" style={{ color: '#5a7a9a' }}>
                      {m.match_date ? formatUkrDate(m.match_date) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/matches/${m.match_id}`} className="hover:text-blue-400 transition-colors">
                        {m.home_team} — {m.away_team}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-center font-mono">{formatScore(m.home_score, m.away_score)}</td>
                    <td className="px-4 py-3 text-center">
                      {m.is_starter == null ? '—' : m.is_starter
                        ? <span style={{ color: '#10B981' }}>✓</span>
                        : <span style={{ color: '#5a7a9a' }}>—</span>}
                    </td>
                    <td className="px-4 py-3 text-center">{m.minutes_played ?? '—'}</td>
                    <td className="px-4 py-3 text-center font-bold" style={{ color: m.goals_in_match > 0 ? '#3B82F6' : '#5a7a9a' }}>
                      {m.goals_in_match > 0 ? m.goals_in_match : '—'}
                    </td>
                    <td className="px-4 py-3 text-center font-bold" style={{ color: m.assists_in_match > 0 ? '#10B981' : '#5a7a9a' }}>
                      {m.assists_in_match > 0 ? m.assists_in_match : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function BioItem({ icon: Icon, label, value }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs flex items-center gap-1" style={{ color: '#5a7a9a' }}>
        {Icon && <Icon className="w-3 h-3" />} {label}
      </span>
      <span className="text-sm font-medium text-white">{value}</span>
    </div>
  );
}

function StatCell({ label, value, color }) {
  return (
    <div className="flex flex-col items-center py-4 px-2">
      <span className="text-xl font-bold" style={{ color: color || '#c8d9ed' }}>{value}</span>
      <span className="text-xs mt-1" style={{ color: '#5a7a9a' }}>{label}</span>
    </div>
  );
}
