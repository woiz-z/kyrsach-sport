import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { UserCircle, Zap, CheckCircle2, XCircle, TrendingUp, CalendarDays } from 'lucide-react';

const RESULT_LABELS = {
  home_win: 'Перемога господарів',
  away_win: 'Перемога гостей',
  draw: 'Нічия',
};

export default function ProfilePage() {
  const { user } = useAuth();
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    api.get('/predictions/my', { params: { limit: 100 } })
      .then(res => setPredictions(res.data))
      .catch((err) => {
        console.error(err);
        setError('Не вдалося завантажити історію прогнозів');
      })
      .finally(() => setLoading(false));
  }, []);

  const total = predictions.length;
  const resolved = predictions.filter(p => p.is_correct !== null && p.is_correct !== undefined);
  const correct = resolved.filter(p => p.is_correct).length;
  const accuracy = resolved.length > 0 ? Math.round((correct / resolved.length) * 100) : null;

  const stats = [
    { label: 'Всього прогнозів', value: total, icon: Zap, color: 'blue' },
    { label: 'Перевірено', value: resolved.length, icon: CalendarDays, color: 'purple' },
    { label: 'Вірних', value: correct, icon: CheckCircle2, color: 'emerald' },
    { label: 'Точність', value: accuracy !== null ? `${accuracy}%` : '—', icon: TrendingUp, color: 'amber' },
  ];

  const COLORS = {
    blue:    { bg: 'bg-blue-50',    icon: 'text-blue-500',    ring: 'ring-blue-200' },
    purple:  { bg: 'bg-purple-50',  icon: 'text-purple-500',  ring: 'ring-purple-200' },
    emerald: { bg: 'bg-emerald-50', icon: 'text-emerald-500', ring: 'ring-emerald-200' },
    amber:   { bg: 'bg-amber-50',   icon: 'text-amber-500',   ring: 'ring-amber-200' },
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-emerald-400 flex items-center justify-center text-white text-3xl font-bold">
          {user?.username?.[0]?.toUpperCase() || 'U'}
        </div>
        <div>
          <h1 className="text-3xl font-bold text-slate-800">{user?.username}</h1>
          <p className="text-slate-500 capitalize">{user?.role} · {user?.email}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(s => {
          const c = COLORS[s.color];
          return (
            <div key={s.label} className={`${c.bg} rounded-2xl p-5 ring-1 ${c.ring}`}>
              <s.icon className={`w-6 h-6 ${c.icon} mb-3`} />
              <p className="text-2xl font-bold text-slate-800">{s.value}</p>
              <p className="text-sm text-slate-500 mt-0.5">{s.label}</p>
            </div>
          );
        })}
      </div>

      {/* Accuracy bar */}
      {accuracy !== null && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <span className="font-semibold text-slate-700">Точність прогнозів</span>
            <span className="text-2xl font-bold text-blue-600">{accuracy}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-3">
            <div
              className="h-3 rounded-full bg-gradient-to-r from-blue-500 to-emerald-400 transition-all duration-700"
              style={{ width: `${accuracy}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 mt-2">{correct} з {resolved.length} перевірених прогнозів вірні</p>
        </div>
      )}

      {/* Prediction History */}
      <div>
        <h2 className="text-xl font-bold text-slate-800 mb-4">Історія прогнозів</h2>
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        ) : predictions.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <Zap className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Ще немає прогнозів. <Link to="/matches" className="text-blue-600 hover:underline">Зробіть перший!</Link></p>
          </div>
        ) : (
          <div className="space-y-3">
            {predictions.map(p => (
              <Link
                key={p.id}
                to={`/matches/${p.match_id}`}
                className="flex items-center gap-4 bg-white rounded-2xl p-4 shadow-sm border border-slate-100 hover:border-blue-200 hover:shadow-md transition-all group"
              >
                {/* Result icon */}
                <div className="shrink-0">
                  {p.is_correct === true && <CheckCircle2 className="w-6 h-6 text-emerald-500" />}
                  {p.is_correct === false && <XCircle className="w-6 h-6 text-red-400" />}
                  {(p.is_correct === null || p.is_correct === undefined) && (
                    <div className="w-6 h-6 rounded-full border-2 border-slate-200 bg-slate-50" />
                  )}
                </div>

                {/* Teams */}
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-800 group-hover:text-blue-600 transition-colors truncate">
                    {p.match?.home_team?.name && p.match?.away_team?.name
                      ? `${p.match.home_team.name} vs ${p.match.away_team.name}`
                      : `Матч #${p.match_id}`}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {p.match?.sport?.name || 'Вид спорту невідомий'}
                    {p.match?.season?.name ? ` · ${p.match.season.name}` : ''}
                  </p>
                </div>

                {/* Prediction */}
                <div className="text-right shrink-0">
                  <p className="text-sm font-medium text-slate-700">{RESULT_LABELS[p.predicted_result] || p.predicted_result}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {Math.round((p.confidence || 0) * 100)}% впевненість
                  </p>
                </div>

                {/* Status badge */}
                <div className="shrink-0">
                  {p.is_correct === true && (
                    <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-medium">Вірно</span>
                  )}
                  {p.is_correct === false && (
                    <span className="px-2 py-1 bg-red-50 text-red-600 rounded-lg text-xs font-medium">Невірно</span>
                  )}
                  {(p.is_correct === null || p.is_correct === undefined) && (
                    <span className="px-2 py-1 bg-slate-50 text-slate-500 rounded-lg text-xs font-medium">Очікується</span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
