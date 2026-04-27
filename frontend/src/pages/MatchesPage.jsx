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
        <h1 className="text-3xl font-bold text-white">Матчі</h1>
        <p className="text-sm mt-1" style={{ color: '#5a7a9a' }}>Розклад та результати спортивних подій</p>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr,220px] md:max-w-2xl">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: '#3d6080' }} />
          <input
            type="text"
            placeholder="Пошук за командою..."
            value={search}
            onChange={handleSearchChange}
            className="dark-input w-full pl-10 pr-4 py-2.5 text-sm"
          />
        </div>
        <select
          value={sportId}
          onChange={handleSportChange}
          className="dark-input w-full px-3 py-2.5 text-sm"
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
            className="px-4 py-2 rounded-xl text-sm font-semibold transition-all"
            style={filter === f.key
              ? { background: 'linear-gradient(135deg,#1D4ED8,#0891B2)', color: '#fff', boxShadow: '0 4px 16px rgba(29,78,216,0.35)' }
              : { background: 'rgba(148,200,255,0.05)', border: '1px solid rgba(148,200,255,0.1)', color: '#5a7a9a' }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(59,130,246,0.2)', borderTopColor: '#3B82F6' }} />
        </div>
      ) : error ? (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>{error}</div>
      ) : (
        <div className="grid gap-3">
          {matches.map(m => (
            <Link
              key={m.id}
              to={`/matches/${m.id}`}
              className="glass-card p-5 hover:border-blue-500/20 transition-all group"
              style={{ display: 'block' }}
            >
              <div className="flex items-center gap-6">
                <div className="flex-1 text-right">
                  <p className="font-bold text-base text-white group-hover:text-blue-400 transition-colors">{m.home_team?.name}</p>
                  <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>{m.home_team?.city}</p>
                </div>

                <div className="shrink-0 text-center space-y-1.5">
                  <div className="flex justify-center">
                    <SportBadge sportName={m.sport?.name} icon={m.sport?.icon} />
                  </div>
                  {m.status === 'completed' ? (
                    <div className="flex items-center gap-2 justify-center">
                      <span className="text-2xl font-bold" style={{ color: m.result === 'home_win' ? '#10B981' : '#E2EEFF' }}>{m.home_score}</span>
                      <span style={{ color: '#3d6080' }}>:</span>
                      <span className="text-2xl font-bold" style={{ color: m.result === 'away_win' ? '#10B981' : '#E2EEFF' }}>{m.away_score}</span>
                    </div>
                  ) : (
                    <div className="px-3 py-1.5 rounded-xl" style={{ background: 'rgba(59,130,246,0.1)' }}>
                      <span className="text-sm font-bold" style={{ color: '#60a5fa' }}>VS</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1 justify-center">
                    <CalendarDays className="w-3 h-3" style={{ color: '#3d6080' }} />
                    <span className="text-xs" style={{ color: '#5a7a9a' }}>{new Date(m.match_date).toLocaleDateString('uk-UA')}</span>
                  </div>
                  {m.status === 'completed' && <StatusBadge result={m.result} />}
                  {m.status === 'scheduled' && (
                    <span className="inline-block px-2 py-0.5 rounded-md text-xs font-medium" style={{ background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>Запланований</span>
                  )}
                </div>

                <div className="flex-1">
                  <p className="font-bold text-base text-white group-hover:text-blue-400 transition-colors">{m.away_team?.name}</p>
                  <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>{m.away_team?.city}</p>
                </div>
              </div>
            </Link>
          ))}
          {matches.length === 0 && (
            <div className="text-center py-12 text-sm" style={{ color: '#5a7a9a' }}>Матчів не знайдено</div>
          )}
        </div>
      )}

      {!loading && (matches.length > 0 || page > 0) && (
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: 'rgba(148,200,255,0.05)', border: '1px solid rgba(148,200,255,0.1)', color: '#5a7a9a' }}
          >
            <ChevronLeft className="w-4 h-4" /> Попередня
          </button>
          <span className="text-sm" style={{ color: '#5a7a9a' }}>Сторінка {page + 1}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={!hasNext}
            className="flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: 'rgba(148,200,255,0.05)', border: '1px solid rgba(148,200,255,0.1)', color: '#5a7a9a' }}
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
    home_win: { label: 'П1', color: '#10B981', bg: 'rgba(16,185,129,0.15)' },
    away_win: { label: 'П2', color: '#EF4444', bg: 'rgba(239,68,68,0.15)' },
    draw:     { label: 'Нічия', color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' },
  };
  const c = cfg[result] || cfg.draw;
  return <span className="inline-block px-2 py-0.5 rounded-md text-xs font-bold" style={{ background: c.bg, color: c.color }}>{c.label}</span>;
}
