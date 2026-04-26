import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, ArrowRight } from 'lucide-react';
import api from '../services/api';

export default function SportHubPage() {
  const [sports, setSports] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.fetchSports().then(setSports).catch((err) => {
      console.error('Failed to load sports:', err);
      setError('Не вдалося завантажити види спорту');
      setSports([]);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-cyan-200 bg-gradient-to-r from-cyan-500 to-blue-500 p-6 text-white shadow-lg shadow-cyan-500/20">
        <div className="flex items-center gap-2 text-cyan-100">
          <Sparkles className="h-5 w-5" />
          Multi-Sport Intelligence
        </div>
        <h1 className="mt-2 text-3xl font-black">Sport Hub</h1>
        <p className="mt-2 max-w-2xl text-cyan-50">
          Огляд усіх видів спорту з єдиним AI-ядром прогнозування. Оберіть категорію,
          щоб перейти до матчів, команд та аналітики.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {sports.map((sport) => (
          <Link
            key={sport.id}
            to={`/matches?sport=${sport.id}`}
            className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
          >
            <div className="flex items-center justify-between">
              <div className="text-4xl">{sport.icon || '🏟️'}</div>
              <ArrowRight className="h-5 w-5 text-slate-400 transition-colors group-hover:text-cyan-600" />
            </div>
            <h2 className="mt-3 text-xl font-bold text-slate-900">{sport.name}</h2>
            <p className="mt-1 text-sm text-slate-500">{sport.description || 'Спортивна категорія'}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
