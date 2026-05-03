import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../services/api';
import { formatUkrDateFull, formatUkrDateTime } from '../utils/date';
import { useAuth } from '../context/AuthContext';
import {
  ArrowLeft, Zap, Trophy, MapPin, CalendarDays, Brain,
  Users, Shirt, Target, Flag, ChevronsUpDown, AlertTriangle, Radio,
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip
} from 'recharts';
import { resolveSportMeta } from '../constants/sports';
import SportBadge from '../components/SportBadge';
import { useToast } from '../components/Toast';
import PlayerAvatar from '../components/PlayerAvatar';

const PIE_COLORS = ['#10b981', '#f59e0b', '#ef4444'];

// ── Live Event Badge ─────────────────────────────────────────────────────────
function EventIcon({ type }) {
  const icons = {
    goal:            '⚽',
    own_goal:        '🥅',
    yellow_card:     '🟨',
    red_card:        '🟥',
    yellow_red_card: '🟧',
    substitution:    '🔄',
    assist:          '🎯',
  };
  return <span className="text-base leading-none">{icons[type] || '•'}</span>;
}

// ── Live Panel ───────────────────────────────────────────────────────────────
function LivePanel({ matchId, initialMatch, onMatchUpdate }) {
  const [liveScore, setLiveScore] = useState({
    home: initialMatch?.home_score ?? null,
    away: initialMatch?.away_score ?? null,
  });
  const [minute, setMinute] = useState(null);
  const [events, setEvents] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [aiText, setAiText] = useState('');
  const [aiStreaming, setAiStreaming] = useState(false);
  const [liveStatus, setLiveStatus] = useState('connecting'); // connecting | live | ended
  const [outcomeLabels, setOutcomeLabels] = useState({
    home_win: 'Перемога госп.',
    away_win: 'Перемога гост.',
    draw: 'Нічия',
  });
  const [allowsDraw, setAllowsDraw] = useState(true);
  const esRef = useRef(null);
  const aiTextRef = useRef('');

  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_URL
      ? import.meta.env.VITE_API_URL.replace(/\/api$/, '')
      : '';
    const url = `${baseUrl}/api/live/${matchId}/stream`;
    const es = new EventSource(url);
    esRef.current = es;
    setLiveStatus('connecting');

    es.onmessage = (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }

      if (msg.type === 'snapshot') {
        setLiveScore({ home: msg.home_score, away: msg.away_score });
        setMinute(msg.minute || null);
        setEvents(msg.all_events || []);
        setPrediction(msg.prediction);
        if (msg.outcome_labels) setOutcomeLabels(msg.outcome_labels);
        if (msg.allows_draw !== undefined) setAllowsDraw(msg.allows_draw);
        const newStatus = msg.status === 'in_progress' ? 'live' : 'ended';
        setLiveStatus(newStatus);
        onMatchUpdate?.({ status: msg.status, home_score: msg.home_score, away_score: msg.away_score });
      }

      if (msg.type === 'event_update') {
        setLiveScore({ home: msg.home_score, away: msg.away_score });
        setMinute(msg.minute || null);
        setEvents(msg.all_events || []);
        setPrediction(msg.prediction);
        if (msg.status === 'completed') {
          setLiveStatus('ended');
          onMatchUpdate?.({ status: 'completed', home_score: msg.home_score, away_score: msg.away_score });
        } else {
          onMatchUpdate?.({ status: msg.status, home_score: msg.home_score, away_score: msg.away_score });
        }
        // Reset AI text for new analysis
        aiTextRef.current = '';
        setAiText('');
        setAiStreaming(true);
      }

      if (msg.type === 'ai_token') {
        aiTextRef.current += msg.token;
        setAiText(aiTextRef.current);
        setAiStreaming(true);
      }

      if (msg.type === 'ai_done') {
        setAiStreaming(false);
      }

      if (msg.type === 'match_ended') {
        setLiveStatus('ended');
        onMatchUpdate?.({ status: 'completed' });
        es.close();
      }
    };

    // On error, EventSource reconnects automatically — don't mark ended or close
    es.onerror = () => {
      // Only update status if we were in connecting state (initial failure)
      setLiveStatus(prev => prev === 'connecting' ? 'connecting' : prev);
    };

    return () => { es.close(); };
  }, [matchId]);

  const homeProb  = prediction ? prediction.home_win_prob * 100 : null;
  const drawProb  = prediction ? prediction.draw_prob * 100 : null;
  const awayProb  = prediction ? prediction.away_win_prob * 100 : null;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(20,8,8,0.4)' }}
    >
      {/* Live header */}
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ background: 'rgba(239,68,68,0.12)', borderBottom: '1px solid rgba(239,68,68,0.2)' }}
      >
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full rounded-full animate-ping opacity-70" style={{ background: '#ef4444' }} />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5" style={{ background: '#ef4444' }} />
          </span>
          <span className="text-sm font-bold tracking-widest uppercase" style={{ color: '#ef4444' }}>
            {liveStatus === 'connecting' ? 'Підключення...' : liveStatus === 'live' ? 'Live' : 'Завершено'}
          </span>
          {minute ? <span className="text-sm font-bold" style={{ color: '#ef4444' }}>{minute}'</span> : null}
        </div>
        <Radio className="w-4 h-4" style={{ color: '#ef4444', opacity: 0.7 }} />
      </div>

      <div className="p-5 space-y-5">
        {/* Live score */}
        <div className="flex items-center justify-center gap-6">
          <span className="text-5xl font-black tabular-nums text-white">{liveScore.home ?? '?'}</span>
          <span className="text-3xl font-black" style={{ color: '#3d6080' }}>:</span>
          <span className="text-5xl font-black tabular-nums text-white">{liveScore.away ?? '?'}</span>
        </div>

        {/* Live probability bars */}
        {prediction && (
          <div className="space-y-2">
            <p className="text-xs font-semibold mb-2" style={{ color: '#5a7a9a' }}>Оновлений AI-прогноз</p>
            <LiveProbBar label={outcomeLabels.home_win} value={homeProb} color="#10b981" />
            {allowsDraw && drawProb > 0 && (
              <LiveProbBar label={outcomeLabels.draw} value={drawProb} color="#f59e0b" />
            )}
            <LiveProbBar label={outcomeLabels.away_win} value={awayProb} color="#ef4444" />
          </div>
        )}

        {/* Events timeline */}
        {events.length > 0 && (
          <div>
            <p className="text-xs font-semibold mb-2" style={{ color: '#5a7a9a' }}>Події матчу</p>
            <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
              {[...events].reverse().map((ev, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="text-xs tabular-nums w-8 text-right shrink-0" style={{ color: '#3d6080' }}>
                    {ev.minute ? `${ev.minute}'` : '—'}
                  </span>
                  <EventIcon type={ev.event_type} />
                  <span className="text-xs truncate" style={{ color: '#93C5FD' }}>{ev.detail}</span>
                  {ev.is_home !== undefined && (
                    <span className="text-[10px] shrink-0" style={{ color: '#3d6080' }}>
                      {ev.is_home ? 'госп.' : 'гост.'}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AI streaming text */}
        {(aiText || aiStreaming) && (
          <div
            className="rounded-xl p-4"
            style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.15)' }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Brain className="w-4 h-4" style={{ color: '#ef4444' }} />
              <span className="text-xs font-bold" style={{ color: '#ef4444' }}>
                AI Коментар{aiStreaming ? '...' : ''}
              </span>
              {aiStreaming && (
                <span className="inline-block w-1 h-4 ml-1 animate-pulse rounded-sm" style={{ background: '#ef4444' }} />
              )}
            </div>
            <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: '#fca5a5' }}>
              {aiText.replace(/\*\*/g, '').replace(/__/g, '')}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function LiveProbBar({ label, value, color }) {
  const pct = Math.min(Math.max(value || 0, 0), 100);
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span style={{ color: '#93C5FD' }}>{label}</span>
        <span className="font-bold" style={{ color }}>{pct.toFixed(1)}%</span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.05)' }}>
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────
export default function MatchDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { addToast } = useToast();
  const [match, setMatch] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [predicting, setPredicting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // Tracks live status/score from SSE without full re-fetch
  const [liveOverride, setLiveOverride] = useState(null);

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

  // Auto-trigger AI prediction when the page loads and there's no prediction yet
  useEffect(() => {
    if (loading || predicting) return;
    if (!match) return;
    if (predictions.length > 0) return;
    // Slight delay so UI renders first
    const t = setTimeout(() => handlePredict(), 800);
    return () => clearTimeout(t);
  }, [loading, match?.id]);

  // Poll match every 30 s while live to update stats/events in the static sections
  useEffect(() => {
    const effectiveStatus = liveOverride?.status ?? match?.status;
    if (effectiveStatus !== 'in_progress') return;
    const timer = setInterval(() => {
      api.get(`/matches/${id}`).then(r => setMatch(r.data)).catch(() => {});
    }, 30_000);
    return () => clearInterval(timer);
  }, [id, match?.status, liveOverride?.status]);

  // Called by LivePanel when SSE delivers score/status changes
  const handleMatchUpdate = ({ status, home_score, away_score } = {}) => {
    setLiveOverride(prev => ({
      ...prev,
      ...(status !== undefined ? { status } : {}),
      ...(home_score !== undefined ? { home_score } : {}),
      ...(away_score !== undefined ? { away_score } : {}),
    }));
  };

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
      <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(59,130,246,0.2)', borderTopColor: '#3B82F6' }} />
    </div>
  );

  if (error) {
    return <div className="text-center py-20" style={{ color: '#EF4444' }}>{error}</div>;
  }

  if (!match) return <div className="text-center py-20" style={{ color: '#5a7a9a' }}>Матч не знайдено</div>;

  const latestPred = predictions[0];
  const sportMeta = resolveSportMeta(match?.sport?.name);
  const outcomeLabels = latestPred?.outcome_labels || {};
  // Merge SSE live overrides so the header reflects real-time state
  const effectiveMatch = liveOverride ? { ...match, ...liveOverride } : match;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Link to="/matches" className="inline-flex items-center gap-2 text-sm transition-colors" style={{ color: '#5a7a9a' }}>
        <ArrowLeft className="w-4 h-4" /> Назад до матчів
      </Link>

      {/* Match Header */}
      <div className="bg-gradient-to-r from-slate-900 to-blue-900 rounded-2xl p-8 text-white">
        <div className="flex items-center gap-2 text-blue-300 text-sm mb-6">
          <SportBadge sportName={effectiveMatch.sport?.name} icon={effectiveMatch.sport?.icon} className="border-white/20 bg-white/10 text-white" />
          <CalendarDays className="w-4 h-4" />
          {formatUkrDateFull(effectiveMatch.match_date)}
          {effectiveMatch.venue && (
            <><span className="mx-2">•</span><MapPin className="w-4 h-4" />{effectiveMatch.venue}</>
          )}
        </div>

        <div className="flex items-center justify-between">
          <div className="flex-1 text-center">
            <div className="w-20 h-20 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center mx-auto mb-3 text-3xl">
              {effectiveMatch?.sport?.icon || sportMeta.icon}
            </div>
            <h2 className="text-xl font-bold">{effectiveMatch.home_team?.name}</h2>
            <p className="text-sm text-blue-300 mt-1">{effectiveMatch.home_team?.city}</p>
          </div>

          <div className="shrink-0 px-8 text-center">
            {effectiveMatch.status === 'completed' ? (
              <>
                <div className="flex items-center gap-4 text-5xl font-bold">
                  <span className={effectiveMatch.result === 'home_win' ? 'text-emerald-400' : ''}>{effectiveMatch.home_score ?? liveOverride?.home_score}</span>
                  <span className="text-white/30">:</span>
                  <span className={effectiveMatch.result === 'away_win' ? 'text-emerald-400' : ''}>{effectiveMatch.away_score ?? liveOverride?.away_score}</span>
                </div>
                <ResultBadge result={effectiveMatch.result} />
              </>
            ) : effectiveMatch.status === 'in_progress' ? (
              <div className="flex items-center gap-2 px-4 py-2 rounded-xl" style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)' }}>
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full rounded-full animate-ping opacity-70" style={{ background: '#ef4444' }} />
                  <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: '#ef4444' }} />
                </span>
                <span className="text-lg font-bold" style={{ color: '#ef4444' }}>LIVE</span>
              </div>
            ) : (
              <div className="px-6 py-3 bg-white/10 backdrop-blur rounded-xl">
                <span className="text-2xl font-bold">VS</span>
              </div>
            )}
          </div>

          <div className="flex-1 text-center">
            <div className="w-20 h-20 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center mx-auto mb-3 text-3xl">
              {effectiveMatch?.sport?.icon || sportMeta.icon}
            </div>
            <h2 className="text-xl font-bold">{effectiveMatch.away_team?.name}</h2>
            <p className="text-sm text-blue-300 mt-1">{effectiveMatch.away_team?.city}</p>
          </div>
        </div>
      </div>

      {/* Live panel — only shown for in_progress matches (or while SSE hasn't ended yet) */}
      {(match.status === 'in_progress' || (liveOverride?.status === 'in_progress')) && (
        <LivePanel matchId={parseInt(id)} initialMatch={match} onMatchUpdate={handleMatchUpdate} />
      )}

      {/* Team Stats Comparison */}
      {match.home_stats?.stats && Object.keys(match.home_stats.stats).length > 0 && (
        <StatsComparison
          homeTeam={effectiveMatch.home_team?.name}
          awayTeam={effectiveMatch.away_team?.name}
          homeStats={match.home_stats.stats}
          awayStats={match.away_stats?.stats || {}}
        />
      )}

      {/* Events Timeline */}
      {match.events?.length > 0 && (
        <EventsTimeline events={match.events} homeTeamId={match.home_team?.id} />
      )}

      {/* Lineups */}
      {(match.home_lineup?.length > 0 || match.away_lineup?.length > 0) && (
        <LineupSection
          homeTeam={effectiveMatch.home_team?.name}
          awayTeam={effectiveMatch.away_team?.name}
          homeLineup={match.home_lineup || []}
          awayLineup={match.away_lineup || []}
        />
      )}

      {/* AI thinking indicator — shown while auto-prediction is running */}
      {predicting && (
        <div className="glass-card p-6 flex items-center gap-4">
          <div className="w-8 h-8 border-2 rounded-full animate-spin shrink-0" style={{ borderColor: 'rgba(245,158,11,0.2)', borderTopColor: '#F59E0B' }} />
          <div>
            <p className="text-sm font-bold text-white">AI думає...</p>
            <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>Аналізуємо статистику та формуємо прогноз</p>
          </div>
          <Brain className="w-6 h-6 ml-auto animate-pulse" style={{ color: '#F59E0B' }} />
        </div>
      )}

      {/* Latest Prediction */}
      {latestPred && (
        <div className="glass-card p-6">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2 text-white">
            <Zap className="w-5 h-5" style={{ color: '#F59E0B' }} /> AI Прогноз
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-medium mb-3" style={{ color: '#5a7a9a' }}>Ймовірності</h4>
              <div className="space-y-3">
                <ProbBar label={outcomeLabels.home_win || `Перемога ${match.home_team?.name}`} value={latestPred.home_win_prob} color="emerald" />
                {latestPred.draw_prob > 0 && <ProbBar label={outcomeLabels.draw || 'Нічия'} value={latestPred.draw_prob} color="amber" />}
                <ProbBar label={outcomeLabels.away_win || `Перемога ${match.away_team?.name}`} value={latestPred.away_win_prob} color="red" />
              </div>

              <div className="mt-4 p-3 rounded-xl" style={{ background: 'rgba(148,200,255,0.05)', border: '1px solid rgba(148,200,255,0.08)' }}>
                <div className="flex items-center justify-between text-sm">
                  <span style={{ color: '#5a7a9a' }}>Прогноз:</span>
                  <ResultBadgeSm result={latestPred.predicted_result} />
                </div>
                <div className="flex items-center justify-between text-sm mt-2">
                  <span style={{ color: '#5a7a9a' }}>Впевненість:</span>
                  <span className="font-bold" style={{ color: '#3B82F6' }}>{((latestPred.confidence || 0) * 100).toFixed(1)}%</span>
                </div>
                <div className="flex items-center justify-between text-sm mt-2">
                  <span style={{ color: '#5a7a9a' }}>Модель:</span>
                  <span className="font-mono text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>{latestPred.model_name}</span>
                </div>
              </div>
            </div>

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
                        { color: '#10b981' },
                        ...(latestPred.draw_prob > 0 ? [{ color: '#f59e0b' }] : []),
                        { color: '#ef4444' },
                      ].map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Pie>
                    <Tooltip
                      formatter={(v) => `${v}%`}
                      contentStyle={{ background: '#0D1B2E', border: '1px solid rgba(148,200,255,0.1)', borderRadius: 8, color: '#E2EEFF' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {latestPred.ai_analysis && !latestPred.ai_analysis.startsWith('AI-аналіз недоступний') && (
            <div className="mt-6 p-5 rounded-xl" style={{ background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)' }}>
              <h4 className="font-bold text-sm text-blue-400 mb-2 flex items-center gap-2">
                <Brain className="w-4 h-4" /> AI Аналіз матчу (Llama 3.3 70B)
              </h4>
              <div className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: '#93C5FD' }}>
                {latestPred.ai_analysis.replace(/\*\*/g, '').replace(/__/g, '')}
              </div>
            </div>
          )}
        </div>
      )}

      {predictions.length > 1 && (
        <div className="glass-card p-6">
          <h3 className="text-lg font-bold mb-4 text-white">Історія прогнозів для цього матчу</h3>
          <div className="space-y-2">
            {predictions.slice(1).map(p => (
              <div key={p.id} className="flex items-center justify-between p-3 rounded-xl text-sm" style={{ background: 'rgba(148,200,255,0.05)', border: '1px solid rgba(148,200,255,0.08)' }}>
                <ResultBadgeSm result={p.predicted_result} />
                <span style={{ color: '#5a7a9a' }}>{((p.confidence || 0) * 100).toFixed(0)}% впевненість</span>
                <span style={{ color: '#3d6080' }}>{formatUkrDateTime(p.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatsComparison({ homeTeam, awayTeam, homeStats, awayStats }) {
  const STAT_LABELS = {
    possessionPct: 'Володіння м\'ячем (%)',
    shots: 'Удари',
    shotsOnTarget: 'Удари в ціль',
    corners: 'Кутові',
    fouls: 'Фоли',
    yellowCards: 'Жовті картки',
    redCards: 'Червоні картки',
    offsides: 'Поза грою',
    saves: 'Сейви',
    passes: 'Паси',
    passAccuracy: 'Точність пасів (%)',
  };

  const rows = Object.entries(STAT_LABELS)
    .map(([key, label]) => {
      const h = parseFloat(homeStats[key] ?? homeStats[key.toLowerCase()] ?? 0) || 0;
      const a = parseFloat(awayStats[key] ?? awayStats[key.toLowerCase()] ?? 0) || 0;
      if (h === 0 && a === 0) return null;
      return { key, label, home: h, away: a };
    })
    .filter(Boolean);

  if (rows.length === 0) return null;

  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-bold mb-5 flex items-center gap-2 text-white">
        <Target className="w-5 h-5" style={{ color: '#10B981' }} /> Статистика матчу
      </h3>
      <div className="flex text-xs font-semibold mb-4 text-center" style={{ color: '#5a7a9a' }}>
        <span className="flex-1 text-left" style={{ color: '#60a5fa' }}>{homeTeam}</span>
        <span className="w-40 text-center" />
        <span className="flex-1 text-right" style={{ color: '#f87171' }}>{awayTeam}</span>
      </div>
      <div className="space-y-4">
        {rows.map(({ key, label, home, away }) => {
          const total = home + away;
          const homeW = total > 0 ? (home / total) * 100 : 50;
          return (
            <div key={key}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="font-semibold text-white w-10 text-left">{home}</span>
                <span style={{ color: '#5a7a9a' }} className="text-xs text-center flex-1">{label}</span>
                <span className="font-semibold text-white w-10 text-right">{away}</span>
              </div>
              <div className="h-2 rounded-full overflow-hidden flex" style={{ background: 'rgba(239,68,68,0.25)' }}>
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${homeW}%`, background: '#3B82F6' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const EVENT_ICON = {
  goal: '⚽',
  yellow_card: '🟨',
  red_card: '🟥',
  substitution: '🔄',
  penalty_goal: '⚽',
  own_goal: '🥅',
};

// ── English → Ukrainian event detail translator ──────────────────────────────
const SHOT_TYPES = [
  [/right footed shot/i, 'удар правою ногою'],
  [/left footed shot/i, 'удар лівою ногою'],
  [/header/i, 'удар головою'],
  [/penalty/i, 'пенальті'],
  [/free kick/i, 'штрафний удар'],
  [/volley/i, 'удар з льоту'],
  [/chip shot/i, 'удар чіпом'],
  [/bicycle kick/i, 'удар через себе'],
  [/tap in/i, 'добивання'],
];
const SHOT_ZONES = [
  [/from outside the box/i, 'з-за штрафного майданчика'],
  [/from the centre of the box/i, 'з центру штрафного майданчика'],
  [/from (?:the )?(?:left|right) side of the box/i, 'зі штрафного майданчика'],
  [/from very close range/i, 'з дуже близької відстані'],
  [/from the penalty spot/i, 'з точки пенальті'],
  [/from (?:close|short) range/i, 'з близької відстані'],
  [/from long range/i, 'з далекої відстані'],
  [/from (?:the )?right(?:\s+side)?/i, 'з правого боку'],
  [/from (?:the )?left(?:\s+side)?/i, 'з лівого боку'],
  [/from (?:the )?centre/i, 'з центру'],
];
const CORNERS = [
  [/(?:to the )?(?:bottom|top)\s+(?:left|right)\s+corner/i, ''],
  [/(?:to the )?(?:left|right)\s+corner/i, ''],
  [/high and wide/i, '(вище та мимо)'],
  [/is close/i, '(близько)'],
  [/misses to the (left|right)/i, '(мимо)'],
  [/saved by/i, 'зупинено воротарем'],
  [/blocked/i, 'заблоковано'],
];
const ASSIST_TYPES = [
  [/with a cross/i, 'з передачею'],
  [/with a through ball/i, 'з пасом за спину'],
  [/with a headed pass/i, 'з верхової передачі'],
  [/with a ?n? ?in-swing corner/i, 'з кутового'],
];
const FOUL_REASONS = [
  [/handball/i, 'гру рукою'],
  [/dangerous play/i, 'небезпечну гру'],
  [/bad foul/i, 'грубе порушення'],
  [/delaying the restart/i, 'затримку відновлення гри'],
  [/simulation/i, 'симуляцію'],
  [/unsporting behaviour/i, 'неспортивну поведінку'],
  [/dissent/i, 'вираження незгоди'],
  [/foul/i, 'порушення'],
];

function translateEventDetail(detail, eventType) {
  if (!detail) return detail;

  // Goal events
  if (eventType === 'goal' || eventType === 'penalty_goal' || eventType === 'own_goal') {
    // Pattern: "Goal! Team1 X, Team2 Y. PlayerName (TeamName) shot..."
    const goalMatch = detail.match(/^Goal!\s*([^,]+),\s*([^.]+)\.\s*(.+)/i);
    if (goalMatch) {
      const score = `${goalMatch[1]}, ${goalMatch[2]}`;
      let rest = goalMatch[3];

      // Extract player + team
      const playerMatch = rest.match(/^(.+?)\s*\(([^)]+)\)\s*(.*)$/);
      if (playerMatch) {
        const player = playerMatch[1].trim();
        const team = playerMatch[2].trim();
        let action = playerMatch[3].trim();

        // Translate shot type
        let shotType = '';
        for (const [re, ukr] of SHOT_TYPES) {
          if (re.test(action)) { shotType = ukr; action = action.replace(re, '').trim(); break; }
        }

        // Translate zone
        let zone = '';
        for (const [re, ukr] of SHOT_ZONES) {
          if (re.test(action)) { zone = ukr; action = action.replace(re, '').trim(); break; }
        }

        // Translate direction
        let direction = '';
        const dirMatch = action.match(/to the (bottom|top)\s*(left|right)\s*corner/i);
        if (dirMatch) {
          const v = dirMatch[1].toLowerCase() === 'top' ? 'верхній' : 'нижній';
          const h = dirMatch[2].toLowerCase() === 'left' ? 'лівий' : 'правий';
          direction = `у ${v} ${h} кут`;
        } else if (/to the (left|right) corner/i.test(action)) {
          const side = /left/i.test(action) ? 'лівий' : 'правий';
          direction = `у ${side} кут`;
        }

        // Extract assist
        let assistText = '';
        const assistMatch = rest.match(/Assisted by ([^.]+?)(?:\s+with (.+?))?\./i);
        if (assistMatch) {
          const assistPlayer = assistMatch[1].trim();
          let assistType = 'передачею';
          if (assistMatch[2]) {
            for (const [re, ukr] of ASSIST_TYPES) {
              if (re.test(assistMatch[2])) { assistType = ukr; break; }
            }
          }
          assistText = ` (асист: ${assistPlayer} — ${assistType})`;
        }

        const prefix = eventType === 'own_goal' ? 'Автогол!' : 'Гол!';
        const parts = [shotType, zone, direction].filter(Boolean).join(', ');
        return `${prefix} ${score}. ${player} (${team})${parts ? ` — ${parts}` : ''}${assistText}.`;
      }
      return `Гол! ${score}.`;
    }

    // Own goal without "Goal!" prefix
    if (eventType === 'own_goal' && /own.?goal/i.test(detail)) {
      return detail
        .replace(/own.?goal/i, 'автогол')
        .replace(/is shown/i, 'отримує')
        .replace(/Goal!/i, 'Гол!');
    }
  }

  // Yellow/Red card: "PlayerName (Team) is shown the yellow/red card for reason."
  if (eventType === 'yellow_card' || eventType === 'yellow_red_card' || eventType === 'red_card') {
    const cardMatch = detail.match(/^(.+?)\s*\(([^)]+)\)\s+is shown the (\w+(?:\s+\w+)?) card(?:\s+for (.+?))?\s*\.?$/i);
    if (cardMatch) {
      const player = cardMatch[1].trim();
      const team = cardMatch[2].trim();
      const cardColor = cardMatch[3].toLowerCase().includes('yellow') ? 'жовту' :
                        cardMatch[3].toLowerCase().includes('red') ? 'червону' : 'картку';
      let reason = '';
      if (cardMatch[4]) {
        let raw = cardMatch[4].trim();
        for (const [re, ukr] of FOUL_REASONS) {
          if (re.test(raw)) { reason = ukr; break; }
        }
        if (!reason) reason = raw;
      }
      const cardType = cardMatch[3].toLowerCase().includes('second yellow') ? 'другу жовту картку' :
                       `${cardColor} картку`;
      return `${player} (${team}) отримує ${cardType}${reason ? ` за ${reason}` : ''}.`;
    }
  }

  // Substitution: "Substitution, Team. PlayerA replaces PlayerB."
  if (eventType === 'substitution') {
    const subMatch = detail.match(/^Substitution(?:,?)\s+(.+?)\.?\s+([^.]+?)\s+replaces\s+([^.]+?)\s*\.?$/i);
    if (subMatch) {
      return `Заміна, ${subMatch[1]}. ${subMatch[2]} замінює ${subMatch[3]}.`;
    }
    const subMatch2 = detail.match(/^(.+?)\s+replaces\s+(.+?)\s*\.?$/i);
    if (subMatch2) {
      return `${subMatch2[1]} замінює ${subMatch2[2]}.`;
    }
  }

  // Fallback: simple word replacements
  return detail
    .replace(/\bGoal!/gi, 'Гол!')
    .replace(/\bAssisted by\b/gi, 'Асист:')
    .replace(/\bis shown the yellow card\b/gi, 'отримує жовту картку')
    .replace(/\bis shown the red card\b/gi, 'отримує червону картку')
    .replace(/\breplaces\b/gi, 'замінює')
    .replace(/\bSubstitution\b/gi, 'Заміна')
    .replace(/\bright footed shot\b/gi, 'удар правою')
    .replace(/\bleft footed shot\b/gi, 'удар лівою')
    .replace(/\bheader\b/gi, 'удар головою');
}

function EventsTimeline({ events, homeTeamId }) {
  const sorted = [...events].sort((a, b) => (a.minute ?? 999) - (b.minute ?? 999));
  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-bold mb-5 flex items-center gap-2 text-white">
        <Flag className="w-5 h-5" style={{ color: '#F59E0B' }} /> Хід матчу
      </h3>
      <div className="space-y-2">
        {sorted.map((ev, idx) => {
          const isHome = ev.team_id === homeTeamId;
          const icon = EVENT_ICON[ev.event_type] || '•';
          const translatedDetail = translateEventDetail(ev.detail, ev.event_type) || ev.event_type;
          return (
            <div key={ev.id ?? idx} className={`flex items-center gap-3 ${isHome ? '' : 'flex-row-reverse'}`}>
              <div className={`flex-1 ${isHome ? 'text-left' : 'text-right'}`}>
                <span className="text-sm text-white">{translatedDetail}</span>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <span className="text-lg">{icon}</span>
                <span className="text-xs font-bold w-8 text-center" style={{ color: '#60a5fa' }}>
                  {ev.minute != null ? `${ev.minute}'` : '—'}
                </span>
              </div>
              <div className="flex-1" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LineupSection({ homeTeam, awayTeam, homeLineup, awayLineup }) {
  const homeStarters = homeLineup.filter(p => p.is_starter);
  const homeBench = homeLineup.filter(p => !p.is_starter);
  const awayStarters = awayLineup.filter(p => p.is_starter);
  const awayBench = awayLineup.filter(p => !p.is_starter);

  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-bold mb-5 flex items-center gap-2 text-white">
        <Users className="w-5 h-5" style={{ color: '#818CF8' }} /> Склади команд
      </h3>
      <div className="grid grid-cols-2 gap-4">
        <LineupColumn team={homeTeam} starters={homeStarters} bench={homeBench} align="left" />
        <LineupColumn team={awayTeam} starters={awayStarters} bench={awayBench} align="right" />
      </div>
    </div>
  );
}

function LineupColumn({ team, starters, bench, align }) {
  const textAlign = align === 'left' ? 'text-left' : 'text-right';
  return (
    <div>
      <h4 className={`font-bold text-sm mb-3 ${textAlign}`} style={{ color: align === 'left' ? '#60a5fa' : '#f87171' }}>{team}</h4>
      {starters.length > 0 && (
        <>
          <p className={`text-[10px] uppercase tracking-wider mb-2 ${textAlign}`} style={{ color: '#3d6080' }}>Стартовий склад</p>
          <div className="space-y-1.5">
            {starters.map((p, i) => (
              <PlayerRow key={p.player_id ?? i} p={p} align={align} />
            ))}
          </div>
        </>
      )}
      {bench.length > 0 && (
        <>
          <p className={`text-[10px] uppercase tracking-wider mb-2 mt-4 ${textAlign}`} style={{ color: '#3d6080' }}>Запас</p>
          <div className="space-y-1.5">
            {bench.map((p, i) => (
              <PlayerRow key={p.player_id ?? i} p={p} align={align} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function PlayerRow({ p, align }) {
  const isLeft = align === 'left';
  return (
    <Link
      to={`/players/${p.player_id}`}
      className={`flex items-center gap-2 text-sm rounded-lg px-1 py-0.5 transition-colors hover:bg-white/5 ${isLeft ? '' : 'flex-row-reverse'}`}
    >
      <PlayerAvatar
        name={p.player_name}
        playerId={p.player_id}
        photoUrl={p.photo_url}
        sizeClass="w-7 h-7"
        textClass="text-[10px]"
      />
      {p.jersey_number != null && (
        <span className="w-6 text-center text-xs font-bold rounded" style={{ background: 'rgba(148,200,255,0.08)', color: '#5a7a9a' }}>
          {p.jersey_number}
        </span>
      )}
      <span className="text-white truncate hover:text-blue-300 transition-colors">{p.player_name || `ID ${p.player_id}`}</span>
      {p.position && (
        <span className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0" style={{ background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>
          {p.position}
        </span>
      )}
    </Link>
  );
}

function ProbBar({ label, value, color }) {
  const pct = (value * 100).toFixed(1);
  const colorMap = {
    emerald: '#10B981',
    amber: '#F59E0B',
    red: '#EF4444',
  };
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span style={{ color: '#5a7a9a' }}>{label}</span>
        <span className="font-bold text-white">{pct}%</span>
      </div>
      <div className="h-3 rounded-full overflow-hidden" style={{ background: 'rgba(148,200,255,0.08)' }}>
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: colorMap[color] }} />
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
    home_win: { label: 'Перемога госп.', color: '#10B981', bg: 'rgba(16,185,129,0.15)' },
    away_win: { label: 'Перемога гост.', color: '#EF4444', bg: 'rgba(239,68,68,0.15)' },
    draw:     { label: 'Нічия', color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' },
  };
  const c = cfg[result] || cfg.draw;
  return <span className="px-2 py-1 rounded-lg text-xs font-medium" style={{ background: c.bg, color: c.color }}>{c.label}</span>;
}
