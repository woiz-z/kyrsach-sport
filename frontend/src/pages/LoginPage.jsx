import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Trophy, LogIn, UserPlus, Eye, EyeOff } from 'lucide-react';

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        await register(username, email, password);
      } else {
        await login(username, password);
      }
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка авторизації');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-emerald-400 mb-4 shadow-xl shadow-blue-500/25">
            <Trophy className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">SportPredict AI</h1>
          <p className="text-slate-400 mt-2">Інформаційна система прогнозування спортивних подій</p>
        </div>

        {/* Form */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-bold mb-6 text-center">
            {isRegister ? 'Реєстрація' : 'Вхід в систему'}
          </h2>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Ім&apos;я користувача</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                placeholder="username"
                required
              />
            </div>

            {isRegister && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                  placeholder="email@example.com"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Пароль</label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all pr-12"
                  placeholder="••••••"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPass ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-xl font-semibold hover:from-blue-700 hover:to-blue-600 transition-all shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : isRegister ? (
                <><UserPlus className="w-5 h-5" /> Зареєструватися</>
              ) : (
                <><LogIn className="w-5 h-5" /> Увійти</>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => { setIsRegister(!isRegister); setError(''); }}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              {isRegister ? 'Вже маєте акаунт? Увійти' : 'Немає акаунту? Зареєструватися'}
            </button>
          </div>

          {!isRegister && (
            <div className="mt-3 text-center">
              <Link to="/forgot-password" className="text-sm text-slate-500 hover:text-blue-600">
                Забули пароль?
              </Link>
            </div>
          )}

          {!isRegister && (
            <div className="mt-4 p-3 bg-slate-50 rounded-xl text-xs text-slate-500 text-center">
              Демо: <span className="font-mono">admin / admin123</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
