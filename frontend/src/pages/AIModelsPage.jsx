import { useState, useEffect } from 'react';
import api from '../services/api';
import {
  Brain, Cpu, CheckCircle2, XCircle, Loader2, BarChart3, RefreshCw, Gauge, FlaskConical
} from 'lucide-react';

export default function AIModelsPage() {
  const [models, setModels] = useState([]);
  const [sportsMap, setSportsMap] = useState({});
  const [algorithms, setAlgorithms] = useState([]);
  const [backtest, setBacktest] = useState(null);
  const [ablation, setAblation] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagError, setDiagError] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(null);
  const [trainingAll, setTrainingAll] = useState(false);

  const loadDiagnostics = async () => {
    setDiagLoading(true);
    setDiagError('');
    try {
      const [bt, ab] = await Promise.all([
        api.get('/ai-models/diagnostics/backtest'),
        api.get('/ai-models/diagnostics/ablation'),
      ]);
      setBacktest(bt.data);
      setAblation(ab.data);
    } catch (err) {
      setBacktest(null);
      setAblation(null);
      setDiagError(err.response?.data?.detail || 'Не вдалося завантажити diagnostics');
    } finally {
      setDiagLoading(false);
    }
  };

  const load = async () => {
    setError('');
    try {
      const [m, a] = await Promise.all([
        api.get('/ai-models/models'),
        api.get('/ai-models/available-algorithms'),
      ]);
      setModels(m.data);
      setAlgorithms(a.data);

      const sports = await api.get('/sports/');
      const map = {};
      (sports.data || []).forEach((s) => { map[s.id] = s.name; });
      setSportsMap(map);
    } catch (err) {
      setError(err.response?.data?.detail || 'Не вдалося завантажити моделі');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleTrain = async (algoName) => {
    setTraining(algoName);
    setError('');
    setSuccess('');
    try {
      await api.post('/ai-models/train', { algorithm: algoName }, { timeout: 120000 });
      setSuccess(`Модель ${algoName} успішно натреновано`);
      await load();
    } catch (err) {
      setError(err.code === 'ECONNABORTED' ? 'Тренування триває довше очікуваного. Спробуйте оновити сторінку за хвилину.' : (err.response?.data?.detail || 'Помилка тренування'));
    } finally {
      setTraining(null);
    }
  };

  const handleActivate = async (modelId) => {
    setError('');
    setSuccess('');
    try {
      await api.patch(`/ai-models/models/${modelId}/activate`);
      setSuccess('Модель успішно активовано');
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка активації');
    }
  };

  const handleTrainBestPerSport = async () => {
    setTrainingAll(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.post('/ai-models/train-best-per-sport', undefined, { timeout: 120000 });
      const trained = res.data?.sports_trained ?? 0;
      const skipped = res.data?.sports_skipped ?? 0;
      setSuccess(skipped > 0
        ? `best-per-sport завершено: натреновано ${trained}, пропущено ${skipped}`
        : `best-per-sport завершено: натреновано ${trained} видів спорту`);
      await load();
    } catch (err) {
      setError(err.code === 'ECONNABORTED' ? 'best-per-sport виконується довше очікуваного. Оновіть сторінку трохи пізніше.' : (err.response?.data?.detail || 'Помилка best-per-sport тренування'));
    } finally {
      setTrainingAll(false);
    }
  };

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">AI Моделі</h1>
        <p className="text-sm text-slate-500 mt-1">Управління моделями машинного навчання для прогнозування</p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {success && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      )}

      {diagError && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {diagError}
        </div>
      )}

      <div>
        <h2 className="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-blue-500" /> Доступні алгоритми
        </h2>
        <div className="mb-4 flex justify-end">
          <button
            onClick={handleTrainBestPerSport}
            disabled={trainingAll || training !== null}
            className="px-4 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl text-sm font-medium hover:from-emerald-700 hover:to-teal-700 transition-all disabled:opacity-50"
          >
            {trainingAll ? 'Тренування по всіх видах...' : 'Train Best Per Sport'}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {algorithms.map(algo => (
            <div key={algo.name} className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-blue-600 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-white" />
                </div>
                <h3 className="font-bold text-slate-800 text-sm">{algo.display_name}</h3>
              </div>
              <p className="text-xs text-slate-500 mb-4 leading-relaxed">{algo.description}</p>
              <button
                onClick={() => handleTrain(algo.name)}
                disabled={training !== null}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl text-sm font-medium hover:from-blue-700 hover:to-blue-800 transition-all disabled:opacity-50"
              >
                {training === algo.name ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Тренування...</>
                ) : (
                  <><RefreshCw className="w-4 h-4" /> Тренувати</>
                )}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Trained Models */}
      <div>
        <h2 className="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-emerald-500" /> Навчені моделі
        </h2>
        {models.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-2xl border border-slate-100">
            <Brain className="w-12 h-12 mx-auto text-slate-300 mb-3" />
            <p className="text-slate-500">Моделей поки немає. Навчіть першу модель вище.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {models.map(model => (
              <div
                key={model.id}
                className={`bg-white rounded-2xl p-5 shadow-sm border-2 transition-colors ${
                  model.is_active ? 'border-emerald-300 bg-emerald-50/30' : 'border-slate-100'
                }`}
              >
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      model.is_active
                        ? 'bg-emerald-100 text-emerald-600'
                        : 'bg-slate-100 text-slate-400'
                    }`}>
                      {model.is_active
                        ? <CheckCircle2 className="w-6 h-6" />
                        : <XCircle className="w-6 h-6" />
                      }
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-800">{model.name}</h3>
                      <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                        <span className="font-mono bg-slate-100 px-2 py-0.5 rounded">{model.algorithm}</span>
                        <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                          {sportsMap[model.parameters?.dataset?.sport_id] || `sport_id=${model.parameters?.dataset?.sport_id ?? '—'}`}
                        </span>
                        <span>{model.trained_at ? new Date(model.trained_at).toLocaleDateString('uk-UA') : '—'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Metrics */}
                  <div className="flex items-center gap-6">
                    {model.parameters?.validation_metrics?.accuracy != null && (
                      <MetricPill label="Val Acc" value={model.parameters.validation_metrics.accuracy} />
                    )}
                    {model.parameters?.validation_metrics?.f1 != null && (
                      <MetricPill label="Val F1" value={model.parameters.validation_metrics.f1} />
                    )}
                    {model.parameters?.cv_accuracy != null && (
                      <MetricPill label="CV Acc" value={model.parameters.cv_accuracy} />
                    )}
                  </div>

                  {!model.is_active && (
                    <button
                      onClick={() => handleActivate(model.id)}
                      className="px-4 py-2 text-sm font-medium text-blue-600 border border-blue-200 rounded-xl hover:bg-blue-50 transition-colors"
                    >
                      Активувати
                    </button>
                  )}
                  {model.is_active && (
                    <span className="px-4 py-2 text-sm font-medium text-emerald-600 bg-emerald-50 rounded-xl border border-emerald-200">
                      Активна
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Diagnostics Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-700 flex items-center gap-2">
            <Gauge className="w-5 h-5 text-indigo-500" /> Діагностика моделей
          </h2>
          <button
            onClick={loadDiagnostics}
            disabled={diagLoading}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            {diagLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Завантаження...</> : <><RefreshCw className="w-4 h-4" /> Запустити діагностику</>}
          </button>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <h2 className="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
            <Gauge className="w-5 h-5 text-indigo-500" /> Rolling Backtest
          </h2>
          {diagLoading ? (
            <div className="py-10 flex justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          ) : backtest?.backtest ? (
            <>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <MetricTile label="Acc" value={backtest.backtest.summary.accuracy} />
                <MetricTile label="F1" value={backtest.backtest.summary.f1} />
                <MetricTile label="Acc std" value={backtest.backtest.summary.accuracy_std} />
                <MetricTile label="Вікна" value={backtest.backtest.summary.windows} isPercent={false} />
              </div>
              <p className="text-xs text-slate-500 mb-3">
                {backtest.season?.name} • {backtest.algorithm} • {backtest.dataset?.samples} матчів
              </p>
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {backtest.backtest.windows.map((w, idx) => (
                  <div key={idx} className="rounded-lg border border-slate-100 px-3 py-2 text-xs flex items-center justify-between">
                    <span className="text-slate-600">train {w.train_samples} / test {w.test_samples}</span>
                    <span className="font-semibold text-slate-800">F1 {(w.f1 * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">Недостатньо даних для rolling backtest.</p>
          )}
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
          <h2 className="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-amber-500" /> Feature Ablation
          </h2>
          {diagLoading ? (
            <div className="py-10 flex justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          ) : ablation?.ablation ? (
            <>
              <div className="mb-4 text-xs text-slate-600">
                Baseline F1: <span className="font-semibold">{(ablation.ablation.baseline.f1 * 100).toFixed(1)}%</span>
              </div>
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {ablation.ablation.groups.map((g) => (
                  <div key={g.group} className="rounded-lg border border-slate-100 px-3 py-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-slate-800">{g.group}</span>
                      <span className={`font-semibold ${g.delta_f1 < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                        ΔF1 {(g.delta_f1 * 100).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">{g.size} фіч • F1 {(g.f1 * 100).toFixed(1)}%</p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">Недостатньо даних для абляційного аналізу.</p>
          )}
        </div>
        </div>
      </div>
    </div>
  );
}

function MetricPill({ label, value }) {
  const pct = (value * 100).toFixed(1);
  const color = value >= 0.7 ? 'text-emerald-600' : value >= 0.5 ? 'text-amber-600' : 'text-red-600';
  return (
    <div className="text-center">
      <p className={`text-lg font-bold ${color}`}>{pct}%</p>
      <p className="text-[10px] text-slate-400 uppercase tracking-wider">{label}</p>
    </div>
  );
}

function MetricTile({ label, value, isPercent = true }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
      <p className="text-lg font-bold text-slate-800">
        {isPercent ? `${((value || 0) * 100).toFixed(1)}%` : value}
      </p>
    </div>
  );
}
