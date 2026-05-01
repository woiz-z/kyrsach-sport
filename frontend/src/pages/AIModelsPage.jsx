import { useState, useEffect } from 'react';
import api from '../services/api';
import { formatUkrDate } from '../utils/date';
import {
  Brain, Cpu, CheckCircle2, XCircle, Loader2, BarChart3, RefreshCw,
  TrendingUp, Zap, Activity, ChevronRight,
} from 'lucide-react';

export default function AIModelsPage() {
  const [status, setStatus] = useState(null);
  const [performance, setPerformance] = useState([]);
  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setError('');
    try {
      const [s, p, r] = await Promise.all([
        api.get('/ai-models/status'),
        api.get('/ai-models/performance'),
        api.get('/ai-models/recent-analyses?limit=8'),
      ]);
      setStatus(s.data);
      setPerformance(p.data || []);
      setRecentAnalyses(r.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Не вдалося завантажити дані AI');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(59,130,246,0.2)', borderTopColor: '#3B82F6' }} />
    </div>
  );

  const totalPredictions = status?.stats?.total_predictions ?? 0;
  const completedMatches = status?.stats?.completed_matches ?? 0;
  const sportsCovered = status?.stats?.sports_covered ?? 0;
  const llmConnected = status?.llm?.connected ?? false;
  const bestAcc = status?.ml?.best_accuracy;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Brain className="w-7 h-7" style={{ color: '#7C3AED' }} />
          AI Аналітик
        </h1>
        <p className="text-sm mt-1" style={{ color: '#5a7a9a' }}>
          Інтелектуальна система аналізу та прогнозування спортивних подій
        </p>
      </div>

      {error && (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>
          {error}
        </div>
      )}

      {/* Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatusCard
          icon={<Zap className="w-5 h-5" />}
          title="LLM Провайдер"
          value={status?.llm?.provider ?? '—'}
          sub={llmConnected ? 'Підключено' : 'Не підключено'}
          ok={llmConnected}
          accent="#7C3AED"
        />
        <StatusCard
          icon={<Brain className="w-5 h-5" />}
          title="ML Модель"
          value={bestAcc != null ? `${(bestAcc * 100).toFixed(1)}%` : '—'}
          sub="Найкраща точність"
          ok={bestAcc != null}
          accent="#3B82F6"
        />
        <StatusCard
          icon={<TrendingUp className="w-5 h-5" />}
          title="Прогнози"
          value={totalPredictions.toLocaleString()}
          sub="Всього зроблено"
          ok={totalPredictions > 0}
          accent="#10B981"
        />
        <StatusCard
          icon={<Activity className="w-5 h-5" />}
          title="Бази даних"
          value={completedMatches.toLocaleString()}
          sub={`${sportsCovered} видів спорту`}
          ok={completedMatches > 0}
          accent="#F59E0B"
        />
      </div>

      {/* LLM Info */}
      <div className="glass-card p-6">
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0"
               style={{ background: 'linear-gradient(135deg,#7C3AED,#1D4ED8)' }}>
            <Brain className="w-7 h-7 text-white" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <h2 className="text-xl font-bold text-white">
                {status?.llm?.model ?? 'llama-3.3-70b-versatile'}
              </h2>
              {llmConnected
                ? <span className="px-2 py-0.5 rounded-full text-xs font-semibold" style={{ background: 'rgba(16,185,129,0.15)', color: '#10B981', border: '1px solid rgba(16,185,129,0.3)' }}>● Активний</span>
                : <span className="px-2 py-0.5 rounded-full text-xs font-semibold" style={{ background: 'rgba(239,68,68,0.1)', color: '#FCA5A5', border: '1px solid rgba(239,68,68,0.2)' }}>● Не підключено</span>
              }
            </div>
            <p className="text-sm" style={{ color: '#5a7a9a' }}>
              Провайдер: <span className="text-white font-medium">{status?.llm?.provider ?? '—'}</span>
            </p>
            <p className="text-sm mt-2 leading-relaxed" style={{ color: '#5a7a9a' }}>
              Аналізує склади команд, статистику сезону, очні зустрічі та події матчу.
              Генерує детальний прогноз українською мовою з поясненням ключових факторів.
            </p>
          </div>
        </div>
      </div>

      {/* Per-Sport Performance */}
      <div>
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2" style={{ color: '#E2EEFF' }}>
          <BarChart3 className="w-5 h-5" style={{ color: '#10B981' }} />
          Точність по видах спорту
        </h2>
        {performance.length === 0 ? (
          <div className="glass-card text-center py-12">
            <BarChart3 className="w-12 h-12 mx-auto mb-3" style={{ color: '#3d6080' }} />
            <p style={{ color: '#5a7a9a' }}>Немає навчених моделей</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {performance.map(p => (
              <SportPerformanceCard key={p.sport_id} p={p} />
            ))}
          </div>
        )}
      </div>

      {/* Recent Analyses */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2" style={{ color: '#E2EEFF' }}>
            <Activity className="w-5 h-5" style={{ color: '#818CF8' }} />
            Останні аналізи
          </h2>
          <button onClick={load} className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg transition-colors"
                  style={{ color: '#60a5fa', border: '1px solid rgba(59,130,246,0.25)' }}>
            <RefreshCw className="w-3.5 h-3.5" /> Оновити
          </button>
        </div>
        {recentAnalyses.length === 0 ? (
          <div className="glass-card text-center py-12">
            <Brain className="w-12 h-12 mx-auto mb-3" style={{ color: '#3d6080' }} />
            <p style={{ color: '#5a7a9a' }}>Прогнозів ще немає. Відкрийте будь-який матч і натисніть «Отримати прогноз».</p>
          </div>
        ) : (
          <div className="space-y-3">
            {recentAnalyses.map(a => (
              <RecentAnalysisRow key={a.id} a={a} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusCard({ icon, title, value, sub, ok, accent }) {
  return (
    <div className="glass-card p-5">
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${accent}22` }}>
          <span style={{ color: accent }}>{icon}</span>
        </div>
        {ok
          ? <CheckCircle2 className="w-4 h-4" style={{ color: '#10B981' }} />
          : <XCircle className="w-4 h-4" style={{ color: '#EF4444' }} />
        }
      </div>
      <p className="text-xs uppercase tracking-wider mb-1" style={{ color: '#3d6080' }}>{title}</p>
      <p className="text-xl font-bold text-white">{value}</p>
      <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>{sub}</p>
    </div>
  );
}

function SportPerformanceCard({ p }) {
  const acc = p.model_accuracy;
  const color = acc == null ? '#3d6080' : acc >= 0.7 ? '#10B981' : acc >= 0.5 ? '#F59E0B' : '#EF4444';
  return (
    <div className="glass-card p-5">
      <div className="flex items-center gap-3 mb-4">
        <span className="text-2xl">{p.sport_icon || '🏆'}</span>
        <div>
          <h3 className="font-bold text-white text-sm">{p.sport_name}</h3>
          <p className="text-xs" style={{ color: '#5a7a9a' }}>
            {p.completed_matches.toLocaleString()} матчів · {p.predictions_made} прогнозів
          </p>
        </div>
        {p.model_trained
          ? <CheckCircle2 className="w-4 h-4 ml-auto flex-shrink-0" style={{ color: '#10B981' }} />
          : <XCircle className="w-4 h-4 ml-auto flex-shrink-0" style={{ color: '#EF4444' }} />
        }
      </div>
      {acc != null ? (
        <div>
          <div className="flex items-center justify-between text-xs mb-1" style={{ color: '#5a7a9a' }}>
            <span>Точність</span>
            <span className="font-semibold" style={{ color }}>{(acc * 100).toFixed(1)}%</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(148,200,255,0.08)' }}>
            <div className="h-full rounded-full transition-all" style={{ width: `${acc * 100}%`, background: color }} />
          </div>
          {p.model_f1 != null && (
            <p className="text-xs mt-2" style={{ color: '#5a7a9a' }}>
              F1: <span className="text-white">{(p.model_f1 * 100).toFixed(1)}%</span>
            </p>
          )}
        </div>
      ) : (
        <p className="text-xs" style={{ color: '#5a7a9a' }}>Модель ще не навчена</p>
      )}
    </div>
  );
}

function RecentAnalysisRow({ a }) {
  const hwp = (a.home_win_probability * 100).toFixed(0);
  const awp = (a.away_win_probability * 100).toFixed(0);
  const dp = a.draw_probability != null ? (a.draw_probability * 100).toFixed(0) : null;
  return (
    <a href={`/matches/${a.match_id}`}
       className="glass-card p-4 flex items-center gap-4 hover:border-blue-500/30 transition-all cursor-pointer"
       style={{ textDecoration: 'none', display: 'flex' }}>
      <span className="text-xl flex-shrink-0">{a.sport_icon || '🏆'}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-semibold text-white text-sm truncate">
            {a.home_team} vs {a.away_team}
          </p>
          {a.has_analysis && (
            <span className="flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium"
                  style={{ background: 'rgba(124,58,237,0.15)', color: '#a78bfa' }}>AI</span>
          )}
        </div>
        <p className="text-xs mt-0.5" style={{ color: '#5a7a9a' }}>
          {a.sport} · {a.match_date ? formatUkrDate(a.match_date) : ''}
        </p>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 text-xs font-semibold">
        <span style={{ color: '#60a5fa' }}>{hwp}%</span>
        {dp != null && <span style={{ color: '#94a3b8' }}>{dp}%</span>}
        <span style={{ color: '#f87171' }}>{awp}%</span>
      </div>
      <ChevronRight className="w-4 h-4 flex-shrink-0" style={{ color: '#3d6080' }} />
    </a>
  );
}

