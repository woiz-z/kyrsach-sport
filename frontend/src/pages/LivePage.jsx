import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { formatUkrDateShort } from '../utils/date';
import { Radio, CalendarDays, MapPin, RefreshCw } from 'lucide-react';
import SportBadge from '../components/SportBadge';
import { useSportMode } from '../context/SportModeContext';

function PulseDot({ color = '#ef4444' }) {
  return (
    <span className="relative flex h-2.5 w-2.5 shrink-0">
      <span
        className="absolute inline-flex h-full w-full rounded-full animate-ping opacity-70"
        style={{ background: color }}
      />
      <span className="relative inline-flex rounded-full h-2.5 w-2.5" style={{ background: color }} />
    </span>
  );
}

function LiveMatchCard({ match }) {
  const { theme } = useSportMode();
  const homeScore = match.home_score ?? '?';
  const awayScore = match.away_score ?? '?';

  return (
    <Link
      to={`/matches/${match.id}`}
      className="glass-card p-5 flex flex-col gap-4 hover:scale-[1.02] transition-transform duration-200 relative overflow-hidden"
      style={{ border: '1px solid rgba(239,68,68,0.25)' }}
    >
      {/* Live badge */}
      <div className="flex items-center justify-between">
        <SportBadge sportName={match.sport?.name} icon={match.sport?.icon} />
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold"
          style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.3)' }}
        >
          <PulseDot />
          LIVE
        </div>
      </div>

      {/* Score */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 text-center">
          <p className="text-sm font-semibold text-white truncate">{match.home_team?.name}</p>
          <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>{match.home_team?.city}</p>
        </div>

        <div className="shrink-0 text-center">
          <div className="flex items-center gap-2">
            <span
              className="text-4xl font-black tabular-nums"
              style={{ color: homeScore > awayScore ? '#10b981' : homeScore === awayScore ? '#e2eeff' : '#5a7a9a' }}
            >
              {homeScore}
            </span>
            <span className="text-2xl font-black" style={{ color: '#3d6080' }}>:</span>
            <span
              className="text-4xl font-black tabular-nums"
              style={{ color: awayScore > homeScore ? '#10b981' : awayScore === homeScore ? '#e2eeff' : '#5a7a9a' }}
            >
              {awayScore}
            </span>
          </div>
          {match.season?.name && (
            <p className="text-[10px] mt-1" style={{ color: '#3d6080' }}>{match.season.name}</p>
          )}
        </div>

        <div className="flex-1 text-center">
          <p className="text-sm font-semibold text-white truncate">{match.away_team?.name}</p>
          <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>{match.away_team?.city}</p>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs" style={{ color: '#3d6080' }}>
        {match.venue ? (
          <span className="flex items-center gap-1">
            <MapPin className="w-3 h-3" /> {match.venue}
          </span>
        ) : (
          <span className="flex items-center gap-1">
            <CalendarDays className="w-3 h-3" />
            {formatUkrDateShort(match.match_date)}
          </span>
        )}
        <span className="text-xs font-semibold" style={{ color: '#3B82F6' }}>
          Слідкувати →
        </span>
      </div>

      {/* Glow effect */}
      <div
        className="absolute inset-0 rounded-2xl pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at top right, rgba(239,68,68,0.06), transparent 60%)' }}
      />
    </Link>
  );
}

export default function LivePage() {
  const { theme, activeSportId, sportMapLoaded } = useSportMode();
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const intervalRef = useRef(null);

  const fetchLive = async () => {
    try {
      const params = {};
      if (activeSportId) params.sport_id = activeSportId;
      const res = await api.get('/live/matches', { params });
      setMatches(Array.isArray(res.data) ? res.data : []);
      setLastUpdated(new Date());
      setError('');
    } catch (err) {
      setError('Не вдалося завантажити живі матчі');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!sportMapLoaded) return;
    fetchLive();
    intervalRef.current = setInterval(fetchLive, 15000);
    return () => clearInterval(intervalRef.current);
  }, [activeSportId, sportMapLoaded]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-5xl font-normal tracking-wider text-white uppercase" style={{ fontFamily: 'var(--font-stat)' }}>Live матчі</h1>
            <div
              className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold"
              style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.3)' }}
            >
              <PulseDot />
              В ЕФІРІ
            </div>
          </div>
          <p className="text-sm" style={{ color: '#5a7a9a' }}>
            AI оновлює прогнози в реальному часі після кожної події
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs" style={{ color: '#3d6080' }}>
              Оновлено {lastUpdated.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button
            onClick={fetchLive}
            className="p-2 rounded-xl transition-colors"
            style={{ background: 'rgba(148,200,255,0.05)', border: '1px solid rgba(148,200,255,0.1)', color: '#5a7a9a' }}
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(239,68,68,0.2)', borderTopColor: '#ef4444' }} />
        </div>
      ) : error ? (
        <div className="text-center py-20" style={{ color: '#EF4444' }}>{error}</div>
      ) : matches.length === 0 ? (
        <div className="glass-card p-16 text-center">
          <Radio className="w-16 h-16 mx-auto mb-4" style={{ color: '#3d6080' }} />
          <h2 className="text-xl font-bold text-white mb-2">Зараз матчів немає</h2>
          <p className="text-sm mb-6" style={{ color: '#5a7a9a' }}>
            Сторінка автоматично оновлюється кожні 15 секунд
          </p>
          <Link
            to="/matches"
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold text-white transition-all"
            style={{ background: theme.gradient, boxShadow: `0 4px 16px ${theme.glow}` }}
          >
            Переглянути розклад
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {matches.map(m => (
            <LiveMatchCard key={m.id} match={m} />
          ))}
        </div>
      )}

      {/* Info block */}
      {matches.length > 0 && (
        <div
          className="rounded-xl p-4 flex items-start gap-3"
          style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.12)' }}
        >
          <Radio className="w-4 h-4 mt-0.5 shrink-0" style={{ color: '#ef4444' }} />
          <p className="text-xs leading-relaxed" style={{ color: '#5a7a9a' }}>
            Натисніть на матч щоб відкрити повний лайв-режим з AI коментарями в реальному часі.
            Прогнози перераховуються автоматично при кожному голі, картці або заміні.
          </p>
        </div>
      )}
    </div>
  );
}
