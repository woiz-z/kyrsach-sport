import { Link } from 'react-router-dom';
import { Home } from 'lucide-react';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="text-center space-y-6">
        <div className="text-8xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
          404
        </div>
        <h1 className="text-2xl font-semibold text-white">Сторінку не знайдено</h1>
        <p className="text-slate-400 max-w-md">
          Сторінка, яку ви шукаєте, не існує або була переміщена.
        </p>
        <div className="flex gap-4 justify-center">
          <Link to="/" className="flex items-center gap-2 px-6 py-3 bg-cyan-500/20 text-cyan-300 rounded-xl hover:bg-cyan-500/30 transition-colors border border-cyan-500/30">
            <Home size={18} />
            На головну
          </Link>
        </div>
      </div>
    </div>
  );
}
