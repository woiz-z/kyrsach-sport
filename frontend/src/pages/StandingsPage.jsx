import { useState, useEffect } from 'react';
import api from '../services/api';
import { Trophy, TrendingUp } from 'lucide-react';
import { useSportMode } from '../context/SportModeContext';

const FORM_COLOR = { W: '#10B981', D: '#F59E0B', L: '#EF4444' };

export default function StandingsPage() {
  const { activeSportId, theme, activeSport } = useSportMode();
  const [seasons, setSeasons] = useState([]);
  const [seasonId, setSeasonId] = useState('');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [seasonsLoading, setSeasonsLoading] = useState(true);
  const [error, setError] = useState('');

  // Load seasons filtered by active sport
  useEffect(() => {
    setError('');
    setSeasonsLoading(true);
    setSeasonId('');
    setRows([]);
    const params = activeSportId ? { sport_id: activeSportId } : {};
    api.get('/sports/seasons', { params })
      .then(res => {
        const s = res.data;
        setSeasons(s);
        if (s.length > 0) setSeasonId(String(s[0].id));
      })
      .catch((err) => {
        console.error(err);
        setError('Не вдалося завантажити список сезонів');
      })
      .finally(() => setSeasonsLoading(false));
  }, [activeSportId, activeSport]);

  // Load standings when season changes
  useEffect(() => {
    if (!seasonId) return;
    setLoading(true);
    setError('');
    api.get(`/teams/standings/${seasonId}`)
      .then(res => setRows(res.data))
      .catch((err) => {
        console.error(err);
        setError('Не вдалося завантажити турнірну таблицю');
      })
      .finally(() => setLoading(false));
  }, [seasonId]);

  const currentSeason = seasons.find(s => String(s.id) === seasonId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-5xl font-normal tracking-wider text-white uppercase" style={{ fontFamily: "var(--font-stat)" }}>Турнірна таблиця</h1>
          <p className="text-sm mt-1" style={{ color: '#5a7a9a' }}>Поточне становище команд у сезоні</p>
        </div>
        {!seasonsLoading && seasons.length > 1 && (
          <select
            value={seasonId}
            onChange={e => setSeasonId(e.target.value)}
            className="dark-input px-4 py-2.5 text-sm"
          >
            {seasons.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        )}
      </div>

      {currentSeason && (
        <div className="flex items-center gap-2 text-sm" style={{ color: '#5a7a9a' }}>
          <Trophy className="w-4 h-4" style={{ color: theme.accent2 }} />
          <span>{currentSeason.name}</span>
        </div>
      )}

      <div className="glass-card overflow-hidden">
        {loading ? (
          <SkeletonTable />
        ) : error ? (
          <div className="px-4 py-3 text-sm rounded-xl m-4" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>{error}</div>
        ) : rows.length === 0 ? (
          <div className="text-center py-16" style={{ color: '#5a7a9a' }}>
            <TrendingUp className="w-12 h-12 mx-auto mb-3" style={{ color: '#3d6080' }} />
            <p>Даних для цього сезону поки немає</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead style={{ background: `${theme.accent}08`, borderBottom: `1px solid ${theme.accent}12` }}>
                <tr className="text-left text-xs uppercase tracking-wider" style={{ color: '#3d6080' }}>
                  <th className="px-4 py-3 font-medium w-10">#</th>
                  <th className="px-4 py-3 font-medium">Команда</th>
                  <th className="px-4 py-3 font-medium text-center">М</th>
                  <th className="px-4 py-3 font-medium text-center">В</th>
                  <th className="px-4 py-3 font-medium text-center">Н</th>
                  <th className="px-4 py-3 font-medium text-center">П</th>
                  <th className="px-4 py-3 font-medium text-center">ГЗ</th>
                  <th className="px-4 py-3 font-medium text-center">ГП</th>
                  <th className="px-4 py-3 font-medium text-center">±</th>
                  <th className="px-4 py-3 font-medium text-center">Форма</th>
                  <th className="px-4 py-3 font-medium text-center" style={{ color: theme.accent }}>Очки</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => {
                  const diff = (row.goals_for ?? 0) - (row.goals_against ?? 0);
                  const isTop3 = idx < 3;
                  const isBottom3 = idx >= rows.length - 3;
                  return (
                    <tr key={row.id} className="transition-colors" style={{ borderBottom: '1px solid rgba(148,200,255,0.05)', background: isTop3 ? `${theme.accent}06` : isBottom3 ? 'rgba(239,68,68,0.04)' : 'transparent' }}>
                      <td className="px-4 py-3 font-bold text-center">
                        {idx + 1 <= 3
                          ? <span style={{ color: theme.accent2 }}>{idx + 1}</span>
                          : idx + 1 >= rows.length - 2
                            ? <span style={{ color: '#EF4444' }}>{idx + 1}</span>
                            : <span style={{ color: '#5a7a9a' }}>{idx + 1}</span>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {row.team?.logo_url ? (
                            <img src={row.team.logo_url} alt={row.team.name} className="w-6 h-6 object-contain rounded" />
                          ) : (
                            <div className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-bold shrink-0" style={{ background: theme.gradient }}>
                              {row.team?.name?.charAt(0)}
                            </div>
                          )}
                          <span className="font-semibold text-white">{row.team?.name ?? `#${row.team_id}`}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center" style={{ color: '#5a7a9a' }}>{row.matches_played}</td>
                      <td className="px-4 py-3 text-center font-medium" style={{ color: '#10B981' }}>{row.wins}</td>
                      <td className="px-4 py-3 text-center" style={{ color: '#F59E0B' }}>{row.draws}</td>
                      <td className="px-4 py-3 text-center" style={{ color: '#EF4444' }}>{row.losses}</td>
                      <td className="px-4 py-3 text-center" style={{ color: '#E2EEFF' }}>{row.goals_for}</td>
                      <td className="px-4 py-3 text-center" style={{ color: '#E2EEFF' }}>{row.goals_against}</td>
                      <td className="px-4 py-3 text-center font-medium" style={{ color: diff > 0 ? '#10B981' : diff < 0 ? '#EF4444' : '#5a7a9a' }}>
                        {diff > 0 ? `+${diff}` : diff}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1 justify-center">
                          {(row.form_last5 ?? []).map((letter, i) => (
                            <span
                              key={i}
                              className="w-5 h-5 rounded-full text-white text-[10px] font-bold flex items-center justify-center"
                              style={{ background: FORM_COLOR[letter] ?? '#3d6080' }}
                            >
                              {letter}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl text-white font-bold text-sm" style={{ background: theme.gradient }}>
                          {row.points}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {rows.length > 0 && (
        <div className="flex items-center gap-6 text-xs" style={{ color: '#5a7a9a' }}>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm inline-block" style={{ background: `${theme.accent}30`, border: `1px solid ${theme.accent}60` }} /> Топ 3 — кваліфікація</div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm inline-block" style={{ background: 'rgba(239,68,68,0.2)', border: '1px solid rgba(239,68,68,0.4)' }} /> Низ 3 — вильот</div>
        </div>
      )}
    </div>
  );
}

function SkeletonTable() {
  return (
    <div className="p-4 space-y-3 animate-pulse">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="flex gap-4 items-center">
          <div className="w-6 h-4 rounded" style={{ background: 'rgba(148,200,255,0.1)' }} />
          <div className="flex-1 h-4 rounded" style={{ background: 'rgba(148,200,255,0.1)' }} />
          <div className="w-8 h-4 rounded" style={{ background: 'rgba(148,200,255,0.1)' }} />
          <div className="w-8 h-4 rounded" style={{ background: 'rgba(148,200,255,0.1)' }} />
          <div className="w-8 h-4 rounded" style={{ background: 'rgba(148,200,255,0.1)' }} />
          <div className="w-8 h-4 rounded" style={{ background: 'rgba(148,200,255,0.1)' }} />
          <div className="w-12 h-4 rounded" style={{ background: 'rgba(148,200,255,0.1)' }} />
        </div>
      ))}
    </div>
  );
}

