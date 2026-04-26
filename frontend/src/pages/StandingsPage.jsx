import { useState, useEffect } from 'react';
import api from '../services/api';
import { Trophy, TrendingUp } from 'lucide-react';

const FORM_COLOR = { W: 'bg-emerald-500', D: 'bg-amber-400', L: 'bg-red-500' };

export default function StandingsPage() {
  const [seasons, setSeasons] = useState([]);
  const [seasonId, setSeasonId] = useState('');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [seasonsLoading, setSeasonsLoading] = useState(true);
  const [error, setError] = useState('');

  // Load all seasons once
  useEffect(() => {
    setError('');
    api.get('/sports/seasons')
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
  }, []);

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
          <h1 className="text-3xl font-bold text-slate-800">Турнірна таблиця</h1>
          <p className="text-slate-500 mt-1">Поточне становище команд у сезоні</p>
        </div>
        {!seasonsLoading && seasons.length > 1 && (
          <select
            value={seasonId}
            onChange={e => setSeasonId(e.target.value)}
            className="px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          >
            {seasons.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        )}
      </div>

      {currentSeason && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Trophy className="w-4 h-4 text-amber-500" />
          <span>{currentSeason.name}</span>
        </div>
      )}

      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        {loading ? (
          <SkeletonTable />
        ) : error ? (
          <div className="px-4 py-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl m-4">{error}</div>
        ) : rows.length === 0 ? (
          <div className="text-center py-16 text-slate-400">
            <TrendingUp className="w-12 h-12 mx-auto mb-3 text-slate-300" />
            <p>Даних для цього сезону поки немає</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr className="text-left text-slate-500 text-xs uppercase tracking-wider">
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
                  <th className="px-4 py-3 font-medium text-center text-blue-600">Очки</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {rows.map((row, idx) => {
                  const diff = (row.goals_for ?? 0) - (row.goals_against ?? 0);
                  const isTop3 = idx < 3;
                  const isBottom3 = idx >= rows.length - 3;
                  return (
                    <tr key={row.id} className={`hover:bg-slate-50 transition-colors ${isTop3 ? 'bg-emerald-50/30' : isBottom3 ? 'bg-red-50/30' : ''}`}>
                      <td className="px-4 py-3 font-bold text-slate-400 text-center">
                        {idx + 1 <= 3
                          ? <span className="text-emerald-600">{idx + 1}</span>
                          : idx + 1 >= rows.length - 2
                            ? <span className="text-red-500">{idx + 1}</span>
                            : idx + 1}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {row.team?.logo_url ? (
                            <img src={row.team.logo_url} alt={row.team.name} className="w-6 h-6 object-contain rounded" />
                          ) : (
                            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-[10px] font-bold shrink-0">
                              {row.team?.name?.charAt(0)}
                            </div>
                          )}
                          <span className="font-semibold text-slate-800">{row.team?.name ?? `#${row.team_id}`}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center text-slate-600">{row.matches_played}</td>
                      <td className="px-4 py-3 text-center text-emerald-600 font-medium">{row.wins}</td>
                      <td className="px-4 py-3 text-center text-amber-600">{row.draws}</td>
                      <td className="px-4 py-3 text-center text-red-500">{row.losses}</td>
                      <td className="px-4 py-3 text-center">{row.goals_for}</td>
                      <td className="px-4 py-3 text-center">{row.goals_against}</td>
                      <td className={`px-4 py-3 text-center font-medium ${diff > 0 ? 'text-emerald-600' : diff < 0 ? 'text-red-500' : 'text-slate-500'}`}>
                        {diff > 0 ? `+${diff}` : diff}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1 justify-center">
                          {(row.form_last5 ?? []).map((letter, i) => (
                            <span
                              key={i}
                              className={`w-5 h-5 rounded-full text-white text-[10px] font-bold flex items-center justify-center ${FORM_COLOR[letter] ?? 'bg-slate-300'}`}
                            >
                              {letter}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-blue-600 text-white font-bold text-sm">
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
        <div className="flex items-center gap-6 text-xs text-slate-500">
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-emerald-100 border border-emerald-300 inline-block" /> Топ 3 — кваліфікація</div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-red-100 border border-red-300 inline-block" /> Низ 3 — вильот</div>
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
          <div className="w-6 h-4 bg-slate-200 rounded" />
          <div className="flex-1 h-4 bg-slate-200 rounded" />
          <div className="w-8 h-4 bg-slate-200 rounded" />
          <div className="w-8 h-4 bg-slate-200 rounded" />
          <div className="w-8 h-4 bg-slate-200 rounded" />
          <div className="w-8 h-4 bg-slate-200 rounded" />
          <div className="w-12 h-4 bg-slate-200 rounded" />
        </div>
      ))}
    </div>
  );
}
