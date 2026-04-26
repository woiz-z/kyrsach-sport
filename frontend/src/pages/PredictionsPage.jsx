import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { Brain, TrendingUp, Calendar, ChevronDown, ChevronUp } from 'lucide-react';

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    api.get('/predictions/').then(res => setPredictions(res.data))
      .catch((err) => {
        console.error(err);
        setError('Не вдалося завантажити прогнози');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Прогнози</h1>
        <span className="text-sm text-slate-500">{predictions.length} прогнозів</span>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : predictions.length === 0 ? (
        <div className="text-center py-16">
          <Brain className="w-12 h-12 mx-auto text-slate-300 mb-3" />
          <p className="text-slate-500">Прогнозів поки немає</p>
          <Link to="/matches" className="inline-block mt-3 text-sm text-blue-600 hover:underline">
            Перейти до матчів →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {predictions.map(pred => (
            <div key={pred.id} className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
              <div
                className="flex items-center justify-between p-5 cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => setExpanded(expanded === pred.id ? null : pred.id)}
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center shrink-0">
                    <Brain className="w-5 h-5 text-white" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-800 truncate">
                      {pred.match?.home_team?.name && pred.match?.away_team?.name
                        ? `${pred.match.home_team.name} vs ${pred.match.away_team.name}`
                        : `Матч #${pred.match_id}`}
                    </p>
                    <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {new Date(pred.created_at).toLocaleString('uk-UA')}
                      </span>
                      <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">
                        {pred.model_name}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <IsCorrectBadge value={pred.is_correct} />
                  <ResultBadge result={pred.predicted_result} />
                  <ConfidenceCircle value={pred.confidence} />
                  {expanded === pred.id
                    ? <ChevronUp className="w-5 h-5 text-slate-400" />
                    : <ChevronDown className="w-5 h-5 text-slate-400" />
                  }
                </div>
              </div>

              {expanded === pred.id && (
                <div className="px-5 pb-5 border-t border-slate-100 pt-4 space-y-4">
                  {/* Probabilities */}
                  <div className={`grid gap-3 ${pred.draw_prob > 0 ? 'grid-cols-3' : 'grid-cols-2'}`}>
                    <ProbCard label="Перемога госп." pct={pred.home_win_prob * 100} color="emerald" />
                    {pred.draw_prob > 0 && <ProbCard label="Нічия" pct={pred.draw_prob * 100} color="amber" />}
                    <ProbCard label="Перемога гост." pct={pred.away_win_prob * 100} color="red" />
                  </div>

                  {/* AI Analysis */}
                  {pred.ai_analysis && !pred.ai_analysis.startsWith('AI-аналіз недоступний') && (
                    <div className="p-4 bg-gradient-to-r from-blue-50 to-emerald-50 rounded-xl border border-blue-100">
                      <h4 className="text-sm font-bold text-blue-800 mb-2 flex items-center gap-2">
                        <Brain className="w-4 h-4" /> AI Аналіз
                      </h4>
                      <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{pred.ai_analysis}</p>
                    </div>
                  )}

                  <Link
                    to={`/matches/${pred.match_id}`}
                    className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
                  >
                    <TrendingUp className="w-4 h-4" /> Переглянути матч →
                  </Link>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function IsCorrectBadge({ value }) {
  if (value === true) return (
    <span className="px-2.5 py-1 rounded-lg text-xs font-semibold border bg-emerald-50 text-emerald-700 border-emerald-200">Вірно ✓</span>
  );
  if (value === false) return (
    <span className="px-2.5 py-1 rounded-lg text-xs font-semibold border bg-red-50 text-red-700 border-red-200">Невірно ✗</span>
  );
  return (
    <span className="px-2.5 py-1 rounded-lg text-xs font-semibold border bg-slate-50 text-slate-500 border-slate-200">Очікується</span>
  );
}

function ProbCard({ label, pct, color }) {
  const colorMap = {
    emerald: 'text-emerald-600 bg-emerald-50 border-emerald-100',
    amber: 'text-amber-600 bg-amber-50 border-amber-100',
    red: 'text-red-600 bg-red-50 border-red-100',
  };
  return (
    <div className={`text-center p-3 rounded-xl border ${colorMap[color]}`}>
      <p className="text-2xl font-bold">{pct.toFixed(1)}%</p>
      <p className="text-xs mt-1">{label}</p>
    </div>
  );
}

function ResultBadge({ result }) {
  const cfg = {
    home_win: { label: 'Госп.', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    away_win: { label: 'Гост.', cls: 'bg-red-50 text-red-700 border-red-200' },
    draw: { label: 'Нічия', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  };
  const c = cfg[result] || cfg.draw;
  return <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border ${c.cls}`}>{c.label}</span>;
}

function ConfidenceCircle({ value }) {
  const pct = ((value || 0) * 100).toFixed(0);
  return (
    <div className="relative w-10 h-10">
      <svg className="w-10 h-10 -rotate-90" viewBox="0 0 36 36">
        <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          fill="none" stroke="#e2e8f0" strokeWidth="3" />
        <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          fill="none" stroke="#3b82f6" strokeWidth="3"
          strokeDasharray={`${pct}, 100`} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-blue-600">
        {pct}%
      </span>
    </div>
  );
}
