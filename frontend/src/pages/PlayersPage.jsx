import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { Search, User } from 'lucide-react';
import { useSportMode } from '../context/SportModeContext';
import PlayerAvatar from '../components/PlayerAvatar';

export default function PlayersPage() {
  const { activeSportId, theme, activeSport } = useSportMode();
  const [players, setPlayers] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const isTennis = activeSport === 'tennis';

  useEffect(() => {
    setError('');
    setLoading(true);
    if (isTennis) {
      // Tennis: players are stored as individual teams
      const params = activeSportId ? { sport_id: activeSportId, limit: 500 } : { limit: 500 };
      api.get('/teams/', { params })
        .then(res => {
          // Map team rows to player-shaped objects
          const mapped = (res.data || []).map(t => ({
            id: t.id,
            name: t.name,
            nationality: t.country || null,
            position: null,
            jersey_number: null,
            photo_url: t.logo_url || null,
            team: null,
            _isTennisPlayer: true,
          }));
          setPlayers(mapped);
        })
        .catch(() => setError('Не вдалося завантажити гравців'))
        .finally(() => setLoading(false));
    } else {
      api.get('/players/', { params: activeSportId ? { sport_id: activeSportId, limit: 200 } : { limit: 200 } })
        .then(res => setPlayers(res.data))
        .catch(() => setError('Не вдалося завантажити гравців'))
        .finally(() => setLoading(false));
    }
  }, [activeSportId, activeSport]);

  const filtered = players.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.nationality || '').toLowerCase().includes(search.toLowerCase()) ||
    (p.team?.name || '').toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 rounded-full animate-spin"
        style={{ borderColor: `${theme.accent}30`, borderTopColor: theme.accent }} />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Гравці</h1>
        <span className="text-sm" style={{ color: '#3d6080' }}>{filtered.length} гравців</span>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: '#3d6080' }} />
        <input
          type="text"
          placeholder="Пошук гравця, команди, країни..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="dark-input w-full pl-10 pr-4 py-2.5 text-sm"
        />
      </div>

      {error ? (
        <div className="rounded-xl px-4 py-3 text-sm"
          style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>
          {error}
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <User className="w-12 h-12 mx-auto mb-3" style={{ color: '#3d6080' }} />
          <p className="text-sm" style={{ color: '#5a7a9a' }}>
            {search ? 'Нічого не знайдено' : 'Гравців немає'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(player => (
            <Link
              key={player.id}
              to={player._isTennisPlayer ? `/teams/${player.id}` : `/players/${player.id}`}
              className="glass-card p-4 flex items-center gap-4 transition-all group hover:scale-[1.02]"
            >
              <PlayerAvatar
                name={player.name}
                photoUrl={player.photo_url}
                playerId={player._isTennisPlayer ? undefined : player.id}
                sizeClass="w-14 h-14 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-white truncate text-sm group-hover:text-blue-300 transition-colors">
                  {player.name}
                </p>
                {player.team && (
                  <p className="text-xs mt-0.5 truncate" style={{ color: theme.accent }}>
                    {player.team.name}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-1 text-[11px]" style={{ color: '#3d6080' }}>
                  {player.position && <span>{player.position}</span>}
                  {player.nationality && (
                    <>
                      {player.position && <span>·</span>}
                      <span>{player.nationality}</span>
                    </>
                  )}
                  {player.jersey_number != null && (
                    <>
                      <span>·</span>
                      <span>#{player.jersey_number}</span>
                    </>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
