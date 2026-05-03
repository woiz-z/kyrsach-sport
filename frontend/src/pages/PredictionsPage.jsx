import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { formatUkrDateTime } from '../utils/date';
import { Brain, TrendingUp, Calendar, ChevronDown, ChevronUp } from 'lucide-react';
import { useSportMode } from '../context/SportModeContext';

export default function PredictionsPage() {
  const { activeSportId, theme, activeSport } = useSportMode();
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    setLoading(true);
    const params = activeSportId ? { sport_id: activeSportId } : {};
    api.get('/predictions/', { params }).then(res => setPredictions(res.data))
      .catch((err) => {
        console.error(err);
        setError('Не вдалося завантажити прогнози');
      })
      .finally(() => setLoading(false));
  }, [activeSportId, activeSport]);

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: `${theme.accent}30`, borderTopColor: theme.accent }} />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-5xl font-normal tracking-wider text-white uppercase" style={{ fontFamily: "var(--font-stat)" }}>Прогнози</h1>
        <span className="text-sm" style={{ color: '#5a7a9a' }}>{predictions.length} прогнозів</span>
      </div>

      {error ? (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>{error}</div>
      ) : predictions.length === 0 ? (
        <div className="text-center py-16">
          <Brain className="w-12 h-12 mx-auto mb-3" style={{ color: '#3d6080' }} />
          <p style={{ color: '#5a7a9a' }}>Прогнозів поки немає</p>
          <Link to="/matches" className="inline-block mt-3 text-sm hover:underline" style={{ color: theme.accent2 }}>
            Перейти до матчів →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {predictions.map(pred => (
            <div key={pred.id} className="glass-card overflow-hidden">
              <div
                className="flex items-center justify-between p-5 cursor-pointer transition-colors"
                onClick={() => setExpanded(expanded === pred.id ? null : pred.id)}
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: theme.gradient }}>
                    <Brain className="w-5 h-5 text-white" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-white truncate">
                      {pred.match?.home_team?.name && pred.match?.away_team?.name
                        ? `${pred.match.home_team.name} vs ${pred.match.away_team.name}`
                        : `Матч #${pred.match_id}`}
                    </p>
                    <div className="flex items-center gap-3 text-xs mt-1" style={{ color: '#5a7a9a' }}>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {formatUkrDateTime(pred.created_at)}
                      </span>
                      <span className="font-mono px-1.5 py-0.5 rounded" style={{ background: `${theme.accent}18`, color: theme.accent2 }}>
                        {pred.model_name}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <IsCorrectBadge value={pred.is_correct} />
                  <ResultBadge result={pred.predicted_result} />
                  <ConfidenceCircle value={pred.confidence} accentColor={theme.accent} />
                  {expanded === pred.id
                    ? <ChevronUp className="w-5 h-5" style={{ color: '#5a7a9a' }} />
                    : <ChevronDown className="w-5 h-5" style={{ color: '#5a7a9a' }} />
                  }
                </div>
              </div>

              {expanded === pred.id && (
                <div className="px-5 pb-5 pt-4 space-y-4" style={{ borderTop: `1px solid ${theme.accent}12` }}>
                  <div className={`grid gap-3 ${pred.draw_prob > 0 ? 'grid-cols-3' : 'grid-cols-2'}`}>
                    <ProbCard label="Перемога госп." pct={pred.home_win_prob * 100} color="emerald" />
                    {pred.draw_prob > 0 && <ProbCard label="Нічия" pct={pred.draw_prob * 100} color="amber" />}
                    <ProbCard label="Перемога гост." pct={pred.away_win_prob * 100} color="red" />
                  </div>

                  {pred.ai_analysis && !pred.ai_analysis.startsWith('AI-аналіз недоступний') && (
                    <div className="p-4 rounded-xl" style={{ background: `${theme.accent}0e`, border: `1px solid ${theme.accent}22` }}>
                      <h4 className="text-sm font-bold mb-2 flex items-center gap-2" style={{ color: theme.accent2 }}>
                        <Brain className="w-4 h-4" /> AI Аналіз
                      </h4>
                      <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: theme.accent2 + 'cc' }}>{pred.ai_analysis}</p>
                    </div>
                  )}

                  <Link
                    to={`/matches/${pred.match_id}`}
                    className="inline-flex items-center gap-1 text-sm hover:underline"
                    style={{ color: theme.accent2 }}
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
    <span className="px-2.5 py-1 rounded-lg text-xs font-semibold" style={{ background: 'rgba(16,185,129,0.15)', color: '#10B981', border: '1px solid rgba(16,185,129,0.3)' }}>Вірно ✓</span>
  );
  if (value === false) return (
    <span className="px-2.5 py-1 rounded-lg text-xs font-semibold" style={{ background: 'rgba(239,68,68,0.15)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.3)' }}>Невірно ✗</span>
  );
  return (
    <span className="px-2.5 py-1 rounded-lg text-xs font-semibold" style={{ background: 'rgba(148,200,255,0.08)', color: '#5a7a9a', border: '1px solid rgba(148,200,255,0.1)' }}>Очікується</span>
  );
}

function ProbCard({ label, pct, color }) {
  const colorMap = {
    emerald: { color: '#10B981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.2)' },
    amber:   { color: '#F59E0B', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.2)' },
    red:     { color: '#EF4444', bg: 'rgba(239,68,68,0.1)',  border: 'rgba(239,68,68,0.2)' },
  };
  const c = colorMap[color];
  return (
    <div className="text-center p-3 rounded-xl" style={{ background: c.bg, border: `1px solid ${c.border}` }}>
      <p className="text-2xl font-bold" style={{ color: c.color }}>{pct.toFixed(1)}%</p>
      <p className="text-xs mt-1" style={{ color: '#5a7a9a' }}>{label}</p>
    </div>
  );
}

function ResultBadge({ result }) {
  const cfg = {
    home_win: { label: 'Госп.', color: '#10B981', bg: 'rgba(16,185,129,0.15)', border: 'rgba(16,185,129,0.3)' },
    away_win: { label: 'Гост.', color: '#EF4444', bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.3)' },
    draw:     { label: 'Нічия', color: '#F59E0B', bg: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.3)' },
  };
  const c = cfg[result] || cfg.draw;
  return <span className="px-2.5 py-1 rounded-lg text-xs font-semibold" style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}` }}>{c.label}</span>;
}

function ConfidenceCircle({ value, accentColor = '#3b82f6' }) {
  const pct = ((value || 0) * 100).toFixed(0);
  return (
    <div className="relative w-10 h-10">
      <svg className="w-10 h-10 -rotate-90" viewBox="0 0 36 36">
        <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          fill="none" stroke={`${accentColor}28`} strokeWidth="3" />
        <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          fill="none" stroke={accentColor} strokeWidth="3"
          strokeDasharray={`${pct}, 100`} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold" style={{ color: accentColor }}>
        {pct}%
      </span>
    </div>
  );
}
