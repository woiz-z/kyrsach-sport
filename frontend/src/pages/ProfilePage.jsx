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
    blue:    { bg: 'rgba(59,130,246,0.1)',  icon: '#3B82F6', border: 'rgba(59,130,246,0.2)' },
    purple:  { bg: 'rgba(168,85,247,0.1)', icon: '#A855F7', border: 'rgba(168,85,247,0.2)' },
    emerald: { bg: 'rgba(16,185,129,0.1)', icon: '#10B981', border: 'rgba(16,185,129,0.2)' },
    amber:   { bg: 'rgba(245,158,11,0.1)', icon: '#F59E0B', border: 'rgba(245,158,11,0.2)' },
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-4">
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-white text-3xl font-bold" style={{ background: 'linear-gradient(135deg, #1D4ED8, #10B981)' }}>
          {user?.username?.[0]?.toUpperCase() || 'U'}
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white">{user?.username}</h1>
          <p className="capitalize" style={{ color: '#5a7a9a' }}>{user?.role} · {user?.email}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(s => {
          const c = COLORS[s.color];
          return (
            <div key={s.label} className="rounded-2xl p-5" style={{ background: c.bg, border: `1px solid ${c.border}` }}>
              <s.icon className="w-6 h-6 mb-3" style={{ color: c.icon }} />
              <p className="text-2xl font-bold text-white">{s.value}</p>
              <p className="text-sm mt-0.5" style={{ color: '#5a7a9a' }}>{s.label}</p>
            </div>
          );
        })}
      </div>

      {accuracy !== null && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-3">
            <span className="font-semibold text-white">Точність прогнозів</span>
            <span className="text-2xl font-bold" style={{ color: '#3B82F6' }}>{accuracy}%</span>
          </div>
          <div className="w-full rounded-full h-3" style={{ background: 'rgba(148,200,255,0.1)' }}>
            <div
              className="h-3 rounded-full transition-all duration-700"
              style={{ width: `${accuracy}%`, background: 'linear-gradient(90deg,#1D4ED8,#10B981)' }}
            />
          </div>
          <p className="text-xs mt-2" style={{ color: '#5a7a9a' }}>{correct} з {resolved.length} перевірених прогнозів вірні</p>
        </div>
      )}

      <div>
        <h2 className="text-xl font-bold text-white mb-4">Історія прогнозів</h2>
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(59,130,246,0.2)', borderTopColor: '#3B82F6' }} />
          </div>
        ) : error ? (
          <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>{error}</div>
        ) : predictions.length === 0 ? (
          <div className="text-center py-12" style={{ color: '#5a7a9a' }}>
            <Zap className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Ще немає прогнозів. <Link to="/matches" className="text-blue-400 hover:underline">Зробіть перший!</Link></p>
          </div>
        ) : (
          <div className="space-y-3">
            {predictions.map(p => (
              <Link
                key={p.id}
                to={`/matches/${p.match_id}`}
                className="glass-card flex items-center gap-4 p-4 hover:border-blue-500/20 transition-all group"
                style={{ display: 'flex' }}
              >
                <div className="shrink-0">
                  {p.is_correct === true && <CheckCircle2 className="w-6 h-6" style={{ color: '#10B981' }} />}
                  {p.is_correct === false && <XCircle className="w-6 h-6" style={{ color: '#EF4444' }} />}
                  {(p.is_correct === null || p.is_correct === undefined) && (
                    <div className="w-6 h-6 rounded-full border-2" style={{ borderColor: 'rgba(148,200,255,0.2)' }} />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-white group-hover:text-blue-400 transition-colors truncate">
                    {p.match?.home_team?.name && p.match?.away_team?.name
                      ? `${p.match.home_team.name} vs ${p.match.away_team.name}`
                      : `Матч #${p.match_id}`}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>
                    {p.match?.sport?.name || 'Вид спорту невідомий'}
                    {p.match?.season?.name ? ` · ${p.match.season.name}` : ''}
                  </p>
                </div>

                <div className="text-right shrink-0">
                  <p className="text-sm font-medium text-white">{RESULT_LABELS[p.predicted_result] || p.predicted_result}</p>
                  <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>
                    {Math.round((p.confidence || 0) * 100)}% впевненість
                  </p>
                </div>

                <div className="shrink-0">
                  {p.is_correct === true && (
                    <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: 'rgba(16,185,129,0.15)', color: '#10B981' }}>Вірно</span>
                  )}
                  {p.is_correct === false && (
                    <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: 'rgba(239,68,68,0.15)', color: '#EF4444' }}>Невірно</span>
                  )}
                  {(p.is_correct === null || p.is_correct === undefined) && (
                    <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: 'rgba(148,200,255,0.08)', color: '#5a7a9a' }}>Очікується</span>
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
