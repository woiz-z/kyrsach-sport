import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import {
  ArrowLeft, Zap, Trophy, MapPin, CalendarDays, Brain, Loader2
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip
} from 'recharts';
import { resolveSportMeta } from '../constants/sports';
import SportBadge from '../components/SportBadge';
import { useToast } from '../components/Toast';

const PIE_COLORS = ['#10b981', '#f59e0b', '#ef4444'];

export default function MatchDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { addToast } = useToast();
  const [match, setMatch] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [predicting, setPredicting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = () => {
    setError('');
    setLoading(true);
    Promise.all([
      api.get(`/matches/${id}`),
      api.get(`/predictions/match/${id}`),
    ]).then(([m, p]) => {
      setMatch(m.data);
      setPredictions(p.data);
    }).catch((err) => {
      console.error(err);
      setError(err.response?.data?.detail || 'Не вдалося завантажити дані матчу');
    })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [id]);

  const handlePredict = async () => {
    setPredicting(true);
    try {
      const res = await api.post('/predictions/predict', { match_id: parseInt(id) });
      setPredictions(prev => [res.data, ...prev]);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Помилка прогнозування', 'error');
    } finally {
      setPredicting(false);
    }
  };

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
    </div>
  );

  if (error) {
    return <div className="text-center py-20 text-red-500">{error}</div>;
  }

  if (!match) return <div className="text-center py-20 text-slate-400">Матч не знайдено</div>;

  const latestPred = predictions[0];
  const sportMeta = resolveSportMeta(match?.sport?.name);
  const outcomeLabels = latestPred?.outcome_labels || {};

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Link to="/matches" className="inline-flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors text-sm">
        <ArrowLeft className="w-4 h-4" /> Назад до матчів
      </Link>

      {/* Match Header */}
      <div className="bg-gradient-to-r from-slate-900 to-blue-900 rounded-2xl p-8 text-white">
        <div className="flex items-center gap-2 text-blue-300 text-sm mb-6">
          <SportBadge sportName={match.sport?.name} icon={match.sport?.icon} className="border-white/20 bg-white/10 text-white" />
          <CalendarDays className="w-4 h-4" />
          {new Date(match.match_date).toLocaleDateString('uk-UA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          {match.venue && (
            <><span className="mx-2">•</span><MapPin className="w-4 h-4" />{match.venue}</>
          )}
        </div>

        <div className="flex items-center justify-between">
          <div className="flex-1 text-center">
            <div className="w-20 h-20 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center mx-auto mb-3 text-3xl">
              {match?.sport?.icon || sportMeta.icon}
            </div>
            <h2 className="text-xl font-bold">{match.home_team?.name}</h2>
            <p className="text-sm text-blue-300 mt-1">{match.home_team?.city}</p>
          </div>

          <div className="shrink-0 px-8 text-center">
            {match.status === 'completed' ? (
              <>
                <div className="flex items-center gap-4 text-5xl font-bold">
                  <span className={match.result === 'home_win' ? 'text-emerald-400' : ''}>{match.home_score}</span>
                  <span className="text-white/30">:</span>
                  <span className={match.result === 'away_win' ? 'text-emerald-400' : ''}>{match.away_score}</span>
                </div>
                <ResultBadge result={match.result} />
              </>
            ) : (
              <div className="px-6 py-3 bg-white/10 backdrop-blur rounded-xl">
                <span className="text-2xl font-bold">VS</span>
              </div>
            )}
          </div>

          <div className="flex-1 text-center">
            <div className="w-20 h-20 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center mx-auto mb-3 text-3xl">
              {match?.sport?.icon || sportMeta.icon}
            </div>
            <h2 className="text-xl font-bold">{match.away_team?.name}</h2>
            <p className="text-sm text-blue-300 mt-1">{match.away_team?.city}</p>
          </div>
        </div>
      </div>

      {/* Predict Button */}
      {user && match?.status !== 'completed' && (
        <div className="text-center">
          <button
            onClick={handlePredict}
            disabled={predicting}
            className="inline-flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-blue-600 to-emerald-500 text-white rounded-xl font-semibold hover:from-blue-700 hover:to-emerald-600 transition-all shadow-lg shadow-blue-500/25 disabled:opacity-50"
          >
            {predicting ? (
              <><Loader2 className="w-5 h-5 animate-spin" /> AI аналізує...</>
            ) : (
              <><Brain className="w-5 h-5" /> Отримати AI прогноз</>
            )}
          </button>
        </div>
      )}

      {/* Latest Prediction */}
      {latestPred && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-500" /> AI Прогноз
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Probabilities */}
            <div>
              <h4 className="text-sm font-medium text-slate-500 mb-3">Ймовірності</h4>
              <div className="space-y-3">
                <ProbBar label={outcomeLabels.home_win || `Перемога ${match.home_team?.name}`} value={latestPred.home_win_prob} color="emerald" />
                {latestPred.draw_prob > 0 && <ProbBar label={outcomeLabels.draw || 'Нічия'} value={latestPred.draw_prob} color="amber" />}
                <ProbBar label={outcomeLabels.away_win || `Перемога ${match.away_team?.name}`} value={latestPred.away_win_prob} color="red" />
              </div>

              <div className="mt-4 p-3 bg-slate-50 rounded-xl">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Прогноз:</span>
                  <ResultBadgeSm result={latestPred.predicted_result} />
                </div>
                <div className="flex items-center justify-between text-sm mt-2">
                  <span className="text-slate-500">Впевненість:</span>
                  <span className="font-bold text-blue-600">{((latestPred.confidence || 0) * 100).toFixed(1)}%</span>
                </div>
                <div className="flex items-center justify-between text-sm mt-2">
                  <span className="text-slate-500">Модель:</span>
                  <span className="font-mono text-xs bg-slate-200 px-2 py-0.5 rounded">{latestPred.model_name}</span>
                </div>
              </div>
            </div>

            {/* Pie Chart */}
            <div className="flex items-center justify-center">
              <div className="w-48 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: outcomeLabels.home_win || 'Пер. госп.', value: +(latestPred.home_win_prob * 100).toFixed(1) },
                        ...(latestPred.draw_prob > 0 ? [{ name: outcomeLabels.draw || 'Нічия', value: +(latestPred.draw_prob * 100).toFixed(1) }] : []),
                        { name: outcomeLabels.away_win || 'Пер. гост.', value: +(latestPred.away_win_prob * 100).toFixed(1) },
                      ]}
                      cx="50%" cy="50%" innerRadius={40} outerRadius={70}
                      dataKey="value"
                    >
                      {[
                        { name: outcomeLabels.home_win || 'Пер. госп.', value: +(latestPred.home_win_prob * 100).toFixed(1), color: '#10b981' },
                        ...(latestPred.draw_prob > 0 ? [{ name: outcomeLabels.draw || 'Нічия', value: +(latestPred.draw_prob * 100).toFixed(1), color: '#f59e0b' }] : []),
                        { name: outcomeLabels.away_win || 'Пер. гост.', value: +(latestPred.away_win_prob * 100).toFixed(1), color: '#ef4444' },
                      ].map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Pie>
                    <Tooltip formatter={(v) => `${v}%`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* AI Analysis */}
          {latestPred.ai_analysis && !latestPred.ai_analysis.startsWith('AI-аналіз недоступний') && (
            <div className="mt-6 p-5 bg-gradient-to-r from-blue-50 to-emerald-50 rounded-xl border border-blue-100">
              <h4 className="font-bold text-sm text-blue-800 mb-2 flex items-center gap-2">
                <Brain className="w-4 h-4" /> AI Аналіз матчу (Llama 3.3 70B)
              </h4>
              <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                {latestPred.ai_analysis}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Prediction History */}
      {predictions.length > 1 && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <h3 className="text-lg font-bold mb-4">Історія прогнозів для цього матчу</h3>
          <div className="space-y-2">
            {predictions.slice(1).map(p => (
              <div key={p.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl text-sm">
                <ResultBadgeSm result={p.predicted_result} />
                <span>{((p.confidence || 0) * 100).toFixed(0)}% впевненість</span>
                <span className="text-slate-400">{new Date(p.created_at).toLocaleString('uk-UA')}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProbBar({ label, value, color }) {
  const pct = (value * 100).toFixed(1);
  const colorMap = {
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  };
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-600">{label}</span>
        <span className="font-bold">{pct}%</span>
      </div>
      <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${colorMap[color]} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ResultBadge({ result }) {
  const cfg = {
    home_win: { label: 'Перемога господарів', cls: 'bg-emerald-500/20 text-emerald-300' },
    away_win: { label: 'Перемога гостей', cls: 'bg-red-500/20 text-red-300' },
    draw: { label: 'Нічия', cls: 'bg-amber-500/20 text-amber-300' },
  };
  const c = cfg[result] || cfg.draw;
  return <span className={`inline-block mt-2 px-3 py-1 rounded-lg text-sm font-medium ${c.cls}`}>{c.label}</span>;
}

function ResultBadgeSm({ result }) {
  const cfg = {
    home_win: { label: 'Перемога госп.', cls: 'bg-emerald-50 text-emerald-700' },
    away_win: { label: 'Перемога гост.', cls: 'bg-red-50 text-red-700' },
    draw: { label: 'Нічия', cls: 'bg-amber-50 text-amber-700' },
  };
  const c = cfg[result] || cfg.draw;
  return <span className={`px-2 py-1 rounded-lg text-xs font-medium ${c.cls}`}>{c.label}</span>;
}
