import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { Search, MapPin, Trophy } from 'lucide-react';

export default function TeamsPage() {
  const [teams, setTeams] = useState([]);
  const [search, setSearch] = useState('');
  const [sports, setSports] = useState([]);
  const [sportFilter, setSportFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    setLoading(true);
    Promise.all([
      api.get('/teams/', { params: sportFilter ? { sport_id: sportFilter } : {} }),
      api.get('/sports/'),
    ]).then(([t, s]) => {
      setTeams(t.data);
      setSports(s.data);
    }).catch((err) => {
      console.error('Failed to load teams:', err);
      setError('Не вдалося завантажити команди');
    }).finally(() => setLoading(false));
  }, [sportFilter]);

  const filtered = teams.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    (t.city || '').toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Команди</h1>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Пошук команди..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        {sports.length > 1 && (
          <select
            value={sportFilter}
            onChange={e => setSportFilter(e.target.value)}
            className="px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            <option value="">Усі види спорту</option>
            {sports.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        )}
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : (
        <>
          {/* Team Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(team => (
              <Link
                key={team.id}
                to={`/teams/${team.id}`}
                className="group bg-white rounded-2xl p-6 shadow-sm border border-slate-100 hover:border-blue-200 hover:shadow-md transition-all"
              >
                <div className="flex items-start gap-4">
                  {team.logo_url ? (
                    <img
                      src={team.logo_url}
                      alt={team.name}
                      className="w-16 h-16 rounded-2xl object-contain bg-slate-50 border border-slate-100 shrink-0"
                    />
                  ) : (
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center text-white text-2xl font-bold shrink-0">
                      {team.name.charAt(0)}
                    </div>
                  )}

                  <div className="min-w-0">
                    <h3 className="font-bold text-slate-800 group-hover:text-blue-600 transition-colors truncate">
                      {team.name}
                    </h3>
                    {team.city && (
                      <p className="text-sm text-slate-500 flex items-center gap-1 mt-1">
                        <MapPin className="w-3.5 h-3.5" /> {team.city}
                      </p>
                    )}
                    {team.founded_year && (
                      <p className="text-sm text-slate-400 flex items-center gap-1 mt-1">
                        <Trophy className="w-3.5 h-3.5" /> Засн. {team.founded_year}
                      </p>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {filtered.length === 0 && (
            <div className="text-center py-12 text-slate-400">
              Команди не знайдено
            </div>
          )}
        </>
      )}
    </div>
  );
}
