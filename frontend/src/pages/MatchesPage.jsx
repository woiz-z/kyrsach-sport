import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { parseAsUTC, ukrDateKey, todayUkrKey, formatUkrTime, formatUkrDate } from '../utils/date';
import { CalendarDays, Search, ChevronLeft, ChevronRight, ArrowRight, Clock3 } from 'lucide-react';
import SportBadge from '../components/SportBadge';
import { useSportMode } from '../context/SportModeContext';

function LiveDot() {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      <span className="absolute inline-flex h-full w-full rounded-full animate-ping opacity-70" style={{ background: '#ef4444' }} />
      <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: '#ef4444' }} />
    </span>
  );
}

function LiveStrip({ matches }) {
  if (!matches.length) return null;
  return (
    <div
      className="rounded-2xl p-4"
      style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.18)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <LiveDot />
        <span className="text-xs font-bold tracking-widest uppercase" style={{ color: '#ef4444' }}>Зараз</span>
        <span className="ml-auto text-xs" style={{ color: '#3d6080' }}>{matches.length} матч{matches.length > 1 ? 'і' : ''}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
        {matches.map(m => (
          <Link
            key={m.id}
            to={`/matches/${m.id}`}
            className="shrink-0 rounded-xl p-3 flex flex-col items-center gap-1.5 min-w-[140px] transition-all hover:scale-[1.03]"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <div className="flex items-center gap-1 text-[10px] font-bold" style={{ color: '#5a7a9a' }}>
              <span>{m.sport?.icon}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-white truncate max-w-[44px]">{m.home_team?.name?.split(' ')[0]}</span>
              <div className="flex items-center gap-1">
                <span className="text-lg font-black tabular-nums" style={{ color: '#e2eeff' }}>{m.home_score ?? '?'}</span>
                <span className="text-sm" style={{ color: '#3d6080' }}>:</span>
                <span className="text-lg font-black tabular-nums" style={{ color: '#e2eeff' }}>{m.away_score ?? '?'}</span>
              </div>
              <span className="text-xs font-semibold text-white truncate max-w-[44px]">{m.away_team?.name?.split(' ')[0]}</span>
            </div>
            <span className="text-[10px] font-semibold" style={{ color: '#3B82F6' }}>Live →</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

const PAGE_SIZE = 20;

function toDateSafe(value) {
  const d = parseAsUTC(value);
  return d && !Number.isNaN(d.getTime()) ? d : null;
}

function getDateSection(matchDate) {
  if (!matchDate) {
    return { key: 'unknown', label: 'Без дати', sortOrder: Number.MAX_SAFE_INTEGER };
  }

  const targetKey = ukrDateKey(matchDate); // 'YYYY-MM-DD' in Kyiv
  const todayKey = todayUkrKey();
  const tomorrowDate = new Date();
  tomorrowDate.setDate(tomorrowDate.getDate() + 1);
  const tomorrowKey = tomorrowDate.toLocaleDateString('sv-SE', { timeZone: 'Europe/Kyiv' });

  const sortOrder = matchDate.getTime();

  if (targetKey === todayKey) {
    return { key: `today-${targetKey}`, label: 'Сьогодні', sortOrder };
  }
  if (targetKey === tomorrowKey) {
    return { key: `tomorrow-${targetKey}`, label: 'Завтра', sortOrder };
  }

  const label = matchDate.toLocaleDateString('uk-UA', { weekday: 'short', day: '2-digit', month: 'long', timeZone: 'Europe/Kyiv' });
  return { key: `date-${targetKey}`, label, sortOrder };
}

function formatKickoff(dateValue) {
  return formatUkrTime(dateValue);
}

function formatMatchDate(dateValue) {
  return formatUkrDate(dateValue);
}

function getStatusLabel(status) {
  if (status === 'in_progress') return 'Live';
  if (status === 'completed') return 'Завершено';
  return 'Заплановано';
}

export default function MatchesPage() {
  const { activeSportId, theme, activeSport } = useSportMode();
  const [matches, setMatches] = useState([]);
  const [liveMatches, setLiveMatches] = useState([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [quickFilter, setQuickFilter] = useState('all');
  const [sortBy, setSortBy] = useState('kickoff_asc');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const liveIntervalRef = useRef(null);

  const fetchMatches = useCallback(() => {
    setLoading(true);
    setError('');
    const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
    if (statusFilter !== 'all') params.status = statusFilter;
    if (activeSportId) params.sport_id = activeSportId;
    if (search.trim()) params.search = search.trim();

    // Pass date range to backend so pagination works correctly for date filters
    const todayStr = todayUkrKey();
    if (quickFilter === 'today') {
      params.date_from = todayStr;
      params.date_to = todayStr;
    } else if (quickFilter === 'this_week') {
      const weekEnd = new Date();
      weekEnd.setDate(weekEnd.getDate() + 6);
      const weekEndStr = weekEnd.toLocaleDateString('sv-SE', { timeZone: 'Europe/Kyiv' });
      params.date_from = todayStr;
      params.date_to = weekEndStr;
    }

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
  }, [statusFilter, search, page, activeSportId, quickFilter]);

  const fetchLive = useCallback(() => {
    const params = {};
    if (activeSportId) params.sport_id = activeSportId;
    api.get('/live/matches', { params })
      .then(res => setLiveMatches(Array.isArray(res.data) ? res.data : []))
      .catch(() => {});
  }, [activeSportId]);

  useEffect(() => { fetchMatches(); }, [fetchMatches]);
  // Auto-refresh match list every 30s so live scores and status changes appear
  useEffect(() => {
    const timer = setInterval(() => fetchMatches(), 30000);
    return () => clearInterval(timer);
  }, [fetchMatches]);
  useEffect(() => {
    fetchLive();
    liveIntervalRef.current = setInterval(fetchLive, 15000);
    return () => clearInterval(liveIntervalRef.current);
  }, [fetchLive]);
  // Reset page when sport or quick filter changes
  useEffect(() => { setPage(0); }, [activeSport, quickFilter]);

  const handleStatusFilterChange = (key) => { setStatusFilter(key); setPage(0); };
  const handleQuickFilterChange = (key) => { setQuickFilter(key); setPage(0); };
  const handleSearchChange = (e) => { setSearch(e.target.value); setPage(0); };

  const statusFilters = [
    { key: 'all', label: 'Усі' },
    { key: 'in_progress', label: 'Live' },
    { key: 'scheduled', label: 'Заплановані' },
    { key: 'completed', label: 'Завершені' },
  ];

  const quickFilters = [
    { key: 'all', label: 'Все' },
    { key: 'today', label: 'На сьогодні' },
    { key: 'this_week', label: 'Цього тижня' },
    { key: 'with_result', label: 'З рахунком' },
  ];

  const filteredAndSorted = useMemo(() => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const endOfWeek = new Date(today);
    endOfWeek.setDate(endOfWeek.getDate() + 7);

    let list = [...matches];

    if (quickFilter !== 'all') {
      list = list.filter((m) => {
        const d = toDateSafe(m.match_date);
        if (quickFilter === 'today') {
          if (!d) return false;
          const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
          return day.getTime() === today.getTime();
        }
        if (quickFilter === 'this_week') {
          if (!d) return false;
          const day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
          return day >= today && day < endOfWeek;
        }
        if (quickFilter === 'with_result') {
          return m.status === 'completed' || typeof m.home_score === 'number' || typeof m.away_score === 'number';
        }
        return true;
      });
    }

    const alpha = (a, b) => `${a ?? ''}`.localeCompare(`${b ?? ''}`, 'uk-UA');
    list.sort((a, b) => {
      const da = toDateSafe(a.match_date)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      const db = toDateSafe(b.match_date)?.getTime() ?? Number.MAX_SAFE_INTEGER;

      if (sortBy === 'live_first') {
        const sa = a.status === 'in_progress' ? 0 : 1;
        const sb = b.status === 'in_progress' ? 0 : 1;
        if (sa !== sb) return sa - sb;
        return da - db;
      }
      if (sortBy === 'team_name') {
        const byHome = alpha(a.home_team?.name, b.home_team?.name);
        if (byHome !== 0) return byHome;
        return alpha(a.away_team?.name, b.away_team?.name);
      }
      if (sortBy === 'kickoff_desc') {
        return db - da;
      }

      return da - db;
    });

    return list;
  }, [matches, quickFilter, sortBy]);

  const groupedMatches = useMemo(() => {
    const sectionsMap = new Map();
    for (const match of filteredAndSorted) {
      const d = toDateSafe(match.match_date);
      const section = getDateSection(d);
      if (!sectionsMap.has(section.key)) {
        sectionsMap.set(section.key, { ...section, items: [] });
      }
      sectionsMap.get(section.key).items.push(match);
    }

    return Array.from(sectionsMap.values()).sort((a, b) => a.sortOrder - b.sortOrder);
  }, [filteredAndSorted]);

  const hasNext = matches.length === PAGE_SIZE;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">Матчі</h1>
        <p className="text-sm mt-1" style={{ color: '#5a7a9a' }}>Розклад та результати спортивних подій</p>
      </div>

      {/* Live strip — only shown when there are in_progress matches */}
      <LiveStrip matches={liveMatches} />

      <div className="space-y-3">
        <div className="flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
          <div className="relative w-full md:max-w-lg">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: '#3d6080' }} />
            <input
              type="text"
              placeholder="Пошук: команда або ліга..."
              value={search}
              onChange={handleSearchChange}
              className="dark-input w-full pl-10 pr-10 py-2.5 text-sm"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 rounded-lg text-xs font-semibold"
                style={{ color: '#5a7a9a', background: 'rgba(148,200,255,0.08)' }}
              >
                Очистити
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <label className="text-xs" style={{ color: '#5a7a9a' }}>Сортування:</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="dark-input text-sm px-3 py-2"
            >
              <option value="kickoff_asc">Найближчі спочатку</option>
              <option value="live_first">Live спочатку</option>
              <option value="kickoff_desc">Пізніші спочатку</option>
              <option value="team_name">За назвою команд</option>
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {quickFilters.map((f) => (
            <button
              key={f.key}
              onClick={() => handleQuickFilterChange(f.key)}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
              style={quickFilter === f.key
                ? { background: 'rgba(59,130,246,0.22)', color: '#dbeafe', border: '1px solid rgba(59,130,246,0.48)' }
                : { background: 'rgba(148,200,255,0.05)', border: '1px solid rgba(148,200,255,0.1)', color: '#5a7a9a' }}
            >
              {f.label}
            </button>
          ))}
          <span className="ml-auto text-xs" style={{ color: '#5a7a9a' }}>
            Знайдено: {filteredAndSorted.length}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {statusFilters.map(f => (
          <button
            key={f.key}
            onClick={() => handleStatusFilterChange(f.key)}
            className="px-4 py-2 rounded-xl text-sm font-semibold transition-all"
            style={statusFilter === f.key
              ? { background: theme.gradient, color: '#fff', boxShadow: `0 4px 16px ${theme.glow}` }
              : { background: 'rgba(148,200,255,0.05)', border: '1px solid rgba(148,200,255,0.1)', color: '#5a7a9a' }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: `${theme.accent}30`, borderTopColor: theme.accent }} />
        </div>
      ) : error ? (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>{error}</div>
      ) : (
        <div className="space-y-4">
          {groupedMatches.map((section) => (
            <div key={section.key} className="space-y-2">
              <div className="sticky top-2 z-10 inline-flex items-center gap-2 px-3 py-1 rounded-full"
                style={{ background: 'rgba(6,14,28,0.82)', border: '1px solid rgba(148,200,255,0.14)' }}
              >
                <CalendarDays className="w-3.5 h-3.5" style={{ color: '#3d6080' }} />
                <span className="text-xs font-semibold" style={{ color: '#9db7d3' }}>{section.label}</span>
                <span className="text-[11px]" style={{ color: '#5a7a9a' }}>{section.items.length}</span>
              </div>

              <div className="grid gap-3">
                {section.items.map((m) => (
                  <Link
                    key={m.id}
                    to={`/matches/${m.id}`}
                    className="glass-card p-4 md:p-5 transition-all group block hover:border-[rgba(148,200,255,0.28)] focus-visible:outline-none"
                  >
                    <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs uppercase tracking-wide font-semibold mb-1.5" style={{ color: '#5a7a9a' }}>
                          {m.league?.name || m.sport?.name || 'Матч'}
                        </p>
                        <div className="flex items-center gap-2 min-w-0">
                          <p className="font-bold text-base md:text-lg text-white truncate">{m.home_team?.name}</p>
                          <span className="text-xs font-semibold" style={{ color: '#3d6080' }}>vs</span>
                          <p className="font-bold text-base md:text-lg text-white truncate">{m.away_team?.name}</p>
                        </div>
                        <p className="text-xs mt-1" style={{ color: '#5a7a9a' }}>
                          {m.home_team?.city || '—'} • {m.away_team?.city || '—'}
                        </p>
                      </div>

                      <div className="shrink-0 flex items-center gap-3 md:gap-4">
                        <div className="text-center min-w-[90px]">
                          <div className="flex items-center justify-center gap-1 mb-1">
                            <Clock3 className="w-3.5 h-3.5" style={{ color: '#3d6080' }} />
                            <span className="text-sm font-semibold" style={{ color: '#c5d7ec' }}>{formatKickoff(m.match_date)}</span>
                          </div>
                          <p className="text-[11px]" style={{ color: '#5a7a9a' }}>{formatMatchDate(m.match_date)}</p>
                        </div>

                        <div className="text-center min-w-[84px]">
                          {m.status === 'completed' || m.status === 'in_progress' ? (
                            <div className="flex items-center justify-center gap-2">
                              <span className="text-2xl font-black tabular-nums" style={{ color: m.result === 'home_win' ? theme.accent2 : '#E2EEFF' }}>{m.home_score ?? 0}</span>
                              <span style={{ color: '#3d6080' }}>:</span>
                              <span className="text-2xl font-black tabular-nums" style={{ color: m.result === 'away_win' ? theme.accent2 : '#E2EEFF' }}>{m.away_score ?? 0}</span>
                            </div>
                          ) : (
                            <div className="px-3 py-1.5 rounded-xl" style={{ background: `${theme.accent}18` }}>
                              <span className="text-sm font-bold" style={{ color: theme.accent2 }}>VS</span>
                            </div>
                          )}
                          <div className="mt-1">
                            {m.status === 'completed' ? <StatusBadge result={m.result} /> : (
                              <span className="inline-block px-2 py-0.5 rounded-md text-xs font-medium" style={{ background: `${theme.accent}18`, color: theme.accent2 }}>
                                {getStatusLabel(m.status)}
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="hidden md:flex flex-col items-end gap-2 min-w-[88px]">
                          <SportBadge sportName={m.sport?.name} icon={m.sport?.icon} />
                          <span className="inline-flex items-center gap-1 text-xs font-semibold group-hover:translate-x-0.5 transition-transform" style={{ color: '#93c5fd' }}>
                            Деталі <ArrowRight className="w-3.5 h-3.5" />
                          </span>
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ))}

          {filteredAndSorted.length === 0 && (
            <div className="text-center py-12">
              <p className="text-sm" style={{ color: '#5a7a9a' }}>Матчів не знайдено за поточними фільтрами</p>
              <button
                type="button"
                onClick={() => {
                  setQuickFilter('all');
                  setStatusFilter('all');
                  setSearch('');
                }}
                className="mt-3 px-4 py-2 rounded-xl text-sm font-semibold"
                style={{ background: 'rgba(148,200,255,0.08)', border: '1px solid rgba(148,200,255,0.2)', color: '#c7daef' }}
              >
                Скинути фільтри
              </button>
            </div>
          )}

          {!loading && filteredAndSorted.length > 0 && (
            <p className="text-xs" style={{ color: '#5a7a9a' }}>
              Порада: використай фільтр «На сьогодні» або «Live спочатку», щоб швидко знайти потрібний матч.
            </p>
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

