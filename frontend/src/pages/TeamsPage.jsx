import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { Search, MapPin, Trophy } from 'lucide-react';
import { useSportMode } from '../context/SportModeContext';

export default function TeamsPage() {
  const { activeSportId, theme, activeSport } = useSportMode();
  const [teams, setTeams] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    setLoading(true);
    api.get('/teams/', { params: activeSportId ? { sport_id: activeSportId } : {} })
      .then(res => setTeams(res.data))
      .catch((err) => {
        console.error('Failed to load teams:', err);
        setError('Не вдалося завантажити команди');
      }).finally(() => setLoading(false));
  }, [activeSportId, activeSport]);

  const filtered = teams.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    (t.city || '').toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: `${theme.accent}30`, borderTopColor: theme.accent }} />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Команди</h1>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: '#3d6080' }} />
        <input
          type="text"
          placeholder="Пошук команди..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="dark-input w-full pl-10 pr-4 py-2.5 text-sm"
        />
      </div>

      {error ? (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>{error}</div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(team => (
              <Link
                key={team.id}
                to={`/teams/${team.id}`}
                className="glass-card p-5 transition-all group"
                style={{ display: 'block' }}
              >
                <div className="flex items-start gap-4">
                  {team.logo_url ? (
                    <img
                      src={team.logo_url}
                      alt={team.name}
                      className="w-14 h-14 rounded-xl object-contain shrink-0"
                      style={{ background: `${theme.accent}10`, border: `1px solid ${theme.accent}20` }}
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-xl flex items-center justify-center text-white text-xl font-bold shrink-0" style={{ background: theme.gradient }}>
                      {team.name.charAt(0)}
                    </div>
                  )}

                  <div className="min-w-0">
                    <h3 className="font-bold text-white transition-colors truncate">
                      {team.name}
                    </h3>
                    {team.city && (
                      <p className="text-sm flex items-center gap-1 mt-1" style={{ color: '#5a7a9a' }}>
                        <MapPin className="w-3.5 h-3.5" /> {team.city}
                      </p>
                    )}
                    {team.founded_year && (
                      <p className="text-sm flex items-center gap-1 mt-1" style={{ color: '#3d6080' }}>
                        <Trophy className="w-3.5 h-3.5" /> Засн. {team.founded_year}
                      </p>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {filtered.length === 0 && (
            <div className="text-center py-12 text-sm" style={{ color: '#5a7a9a' }}>
              Команди не знайдено
            </div>
          )}
        </>
      )}
    </div>
  );
}
