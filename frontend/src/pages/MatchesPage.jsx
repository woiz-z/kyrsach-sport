import { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import api from '../services/api';
import { CalendarDays, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import SportBadge from '../components/SportBadge';

const PAGE_SIZE = 20;

export default function MatchesPage() {
  const [searchParams] = useSearchParams();
  const initialSport = searchParams.get('sport') || 'all';
  const [matches, setMatches] = useState([]);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [sports, setSports] = useState([]);
  const [sportId, setSportId] = useState(initialSport);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchMatches = useCallback(() => {
    setLoading(true);
    setError('');
    const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
    if (filter !== 'all') params.status = filter;
    if (sportId !== 'all') params.sport_id = Number(sportId);
    if (search.trim()) params.search = search.trim();
    api.get('/matches/', { params })
      .then(res => {
        const data = Array.isArray(res.data) ? res.data : (res.data.items ?? []);
        setMatches(data);
      })
      .catch((err) => {
        console.error(err);
        setError('Не вдалося завантажити матчі');
      })
      .finally(() => setLoading(false));
  }, [filter, search, page, sportId]);

  useEffect(() => { fetchMatches(); }, [fetchMatches]);

  useEffect(() => {
    api.fetchSports().then(setSports).catch(() => setSports([]));
  }, []);

  const handleFilterChange = (key) => { setFilter(key); setPage(0); };
  const handleSearchChange = (e) => { setSearch(e.target.value); setPage(0); };
  const handleSportChange = (e) => { setSportId(e.target.value); setPage(0); };

  const statusFilters = [
    { key: 'all', label: 'Усі' },
    { key: 'scheduled', label: 'Заплановані' },
    { key: 'completed', label: 'Завершені' },
  ];

  const hasNext = matches.length === PAGE_SIZE;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-800">Матчі</h1>
        <p className="text-slate-500 mt-1">Розклад та результати спортивних подій</p>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr,220px] md:max-w-2xl">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Пошук за командою..."
            value={search}
            onChange={handleSearchChange}
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500"
          />
        </div>
        <select
          value={sportId}
          onChange={handleSportChange}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500"
        >
          <option value="all">Усі види спорту</option>
          {sports.map((sport) => (
            <option key={sport.id} value={sport.id}>{sport.icon ? `${sport.icon} ` : ''}{sport.name}</option>
          ))}
        </select>
      </div>

      <div className="flex gap-2">
        {statusFilters.map(f => (
          <button
            key={f.key}
            onClick={() => handleFilterChange(f.key)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filter === f.key
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25'
                : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : (
        <div className="grid gap-4">
          {matches.map(m => (
            <Link
              key={m.id}
              to={`/matches/${m.id}`}
              className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-all hover:border-blue-200 group"
            >
              <div className="flex items-center gap-6">
                <div className="flex-1 text-right">
                  <p className="font-bold text-lg group-hover:text-blue-600 transition-colors">{m.home_team?.name}</p>
                  <p className="text-xs text-slate-400">{m.home_team?.city}</p>
                </div>

                <div className="shrink-0 text-center">
                  <SportBadge
                    sportName={m.sport?.name}
                    icon={m.sport?.icon}
                    className="mb-2"
                  />
                  {m.status === 'completed' ? (
                    <div className="flex items-center gap-2">
                      <span className={`text-2xl font-bold ${m.result === 'home_win' ? 'text-emerald-500' : 'text-slate-800'}`}>
                        {m.home_score}
                      </span>
                      <span className="text-slate-300">:</span>
                      <span className={`text-2xl font-bold ${m.result === 'away_win' ? 'text-emerald-500' : 'text-slate-800'}`}>
                        {m.away_score}
                      </span>
                    </div>
                  ) : (
                    <div className="px-4 py-2 bg-gradient-to-r from-blue-50 to-emerald-50 rounded-xl">
                      <span className="text-sm font-bold text-blue-600">VS</span>
                    </div>
                  )}

                  <div className="flex items-center gap-1 mt-1 justify-center">
                    <CalendarDays className="w-3 h-3 text-slate-400" />
                    <span className="text-xs text-slate-400">
                      {new Date(m.match_date).toLocaleDateString('uk-UA')}
                    </span>
                  </div>

                  {m.status === 'completed' && <StatusBadge result={m.result} />}
                  {m.status === 'scheduled' && (
                    <span className="inline-block mt-1 px-2 py-0.5 bg-blue-50 text-blue-600 rounded-md text-xs font-medium">
                      Запланований
                    </span>
                  )}
                </div>

                <div className="flex-1">
                  <p className="font-bold text-lg group-hover:text-blue-600 transition-colors">{m.away_team?.name}</p>
                  <p className="text-xs text-slate-400">{m.away_team?.city}</p>
                </div>
              </div>
            </Link>
          ))}

          {matches.length === 0 && (
            <div className="text-center py-12 text-slate-400">Матчів не знайдено</div>
          )}
        </div>
      )}

      {!loading && (matches.length > 0 || page > 0) && (
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex items-center gap-1 px-4 py-2 rounded-xl border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            <ChevronLeft className="w-4 h-4" /> Попередня
          </button>

          <span className="text-sm text-slate-500">Сторінка {page + 1}</span>

          <button
            onClick={() => setPage(p => p + 1)}
            disabled={!hasNext}
            className="flex items-center gap-1 px-4 py-2 rounded-xl border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            Наступна <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ result }) {
  const cfg = {
    home_win: { label: 'Перемога господарів', cls: 'bg-emerald-50 text-emerald-700' },
    away_win: { label: 'Перемога гостей', cls: 'bg-red-50 text-red-700' },
    draw: { label: 'Нічия', cls: 'bg-amber-50 text-amber-700' },
  };
  const c = cfg[result] || cfg.draw;
  return <span className={`inline-block mt-1 px-2 py-0.5 rounded-md text-xs font-medium ${c.cls}`}>{c.label}</span>;
}
