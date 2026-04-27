import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Trophy, LogIn, UserPlus, Eye, EyeOff, Zap } from 'lucide-react';

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
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: '#060E1C' }}>
      {/* Background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full opacity-20"
          style={{ background: 'radial-gradient(circle, #3B82F6 0%, transparent 70%)', filter: 'blur(40px)' }} />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full opacity-15"
          style={{ background: 'radial-gradient(circle, #8B5CF6 0%, transparent 70%)', filter: 'blur(40px)' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full opacity-5"
          style={{ background: 'radial-gradient(circle, #06B6D4 0%, transparent 70%)', filter: 'blur(60px)' }} />
      </div>

      <div className="w-full max-w-md relative z-10 animate-float-up">
        {/* Logo */}
        <div className="text-center mb-8">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4 animate-pulse-glow"
            style={{ background: 'linear-gradient(135deg, #3B82F6 0%, #06B6D4 100%)', boxShadow: '0 0 30px rgba(59,130,246,0.5)' }}
          >
            <Trophy className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">SportPredict <span className="gradient-text">AI</span></h1>
          <p className="mt-2 text-sm" style={{ color: '#5a7a9a' }}>Інформаційна система прогнозування спортивних подій</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl p-8" style={{ background: '#0D1B2E', border: '1px solid rgba(148,200,255,0.1)' }}>
          <h2 className="text-lg font-bold text-white mb-6 text-center">
            {isRegister ? 'Створити акаунт' : 'Вхід в систему'}
          </h2>

          {error && (
            <div className="mb-5 p-3 rounded-xl text-sm border" style={{ background: 'rgba(239,68,68,0.1)', borderColor: 'rgba(239,68,68,0.2)', color: '#FCA5A5' }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wider" style={{ color: '#5a7a9a' }}>
                Ім&apos;я користувача
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="dark-input w-full px-4 py-3 text-sm"
                placeholder="username"
                required
              />
            </div>

            {isRegister && (
              <div>
                <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wider" style={{ color: '#5a7a9a' }}>
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="dark-input w-full px-4 py-3 text-sm"
                  placeholder="email@example.com"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wider" style={{ color: '#5a7a9a' }}>
                Пароль
              </label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="dark-input w-full px-4 py-3 pr-12 text-sm"
                  placeholder="••••••••"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
                  style={{ color: '#3d6080' }}
                >
                  {showPass ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl font-bold text-sm text-white flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #1D4ED8 0%, #0891B2 100%)', boxShadow: '0 4px 20px rgba(29,78,216,0.4)' }}
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : isRegister ? (
                <><UserPlus className="w-4 h-4" /> Зареєструватися</>
              ) : (
                <><LogIn className="w-4 h-4" /> Увійти</>
              )}
            </button>
          </form>

          <div className="mt-5 text-center">
            <button
              onClick={() => { setIsRegister(!isRegister); setError(''); }}
              className="text-sm transition-colors hover:text-blue-300"
              style={{ color: '#3B82F6' }}
            >
              {isRegister ? 'Вже маєте акаунт? Увійти' : 'Немає акаунту? Зареєструватися'}
            </button>
          </div>

          {!isRegister && (
            <div className="mt-3 text-center">
              <Link to="/forgot-password" className="text-xs transition-colors hover:text-blue-400" style={{ color: '#3d6080' }}>
                Забули пароль?
              </Link>
            </div>
          )}

          {/* Features hint */}
          <div className="mt-6 pt-5 grid grid-cols-3 gap-3" style={{ borderTop: '1px solid rgba(148,200,255,0.06)' }}>
            {['AI прогнози', 'Мульти-спорт', 'Аналітика'].map((feat, i) => (
              <div key={i} className="text-center">
                <Zap className="w-4 h-4 mx-auto mb-1" style={{ color: ['#3B82F6', '#10B981', '#8B5CF6'][i] }} />
                <p className="text-[10px]" style={{ color: '#3d6080' }}>{feat}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


