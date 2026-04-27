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
      <div className="rounded-2xl p-6 text-white" style={{ background: 'linear-gradient(135deg, #0D1B2E 0%, #1D4ED8 50%, #0891B2 100%)', border: '1px solid rgba(59,130,246,0.3)', boxShadow: '0 8px 32px rgba(29,78,216,0.3)' }}>
        <div className="flex items-center gap-2 text-blue-200 text-sm mb-2">
          <Sparkles className="h-4 w-4" />
          Multi-Sport Intelligence
        </div>
        <h1 className="mt-1 text-3xl font-black">Sport Hub</h1>
        <p className="mt-2 max-w-2xl text-blue-100 text-sm">
          Огляд усіх видів спорту з єдиним AI-ядром прогнозування.
        </p>
      </div>

      {error && (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#FCA5A5' }}>
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {sports.map((sport) => (
          <Link
            key={sport.id}
            to={`/matches?sport=${sport.id}`}
            className="glass-card p-5 transition-all hover:border-blue-500/20 group"
            style={{ display: 'block' }}
          >
            <div className="flex items-center justify-between">
              <div className="text-4xl">{sport.icon || '🏟'}</div>
              <ArrowRight className="h-5 w-5 transition-colors" style={{ color: '#3d6080' }} />
            </div>
            <h2 className="mt-3 text-lg font-bold text-white group-hover:text-blue-400 transition-colors">{sport.name}</h2>
            <p className="mt-1 text-sm" style={{ color: '#5a7a9a' }}>{sport.description || 'Спортивна категорія'}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
