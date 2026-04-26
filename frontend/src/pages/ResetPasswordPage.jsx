import { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Trophy, KeyRound, Eye, EyeOff, ArrowLeft } from 'lucide-react';
import api from '../services/api';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirm) {
      setError('Паролі не збігаються');
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/reset-password', { token, new_password: password });
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка. Спробуйте ще раз.');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full text-center">
          <p className="text-red-600 font-medium mb-4">Токен скидання пароля відсутній або недійсний.</p>
          <Link to="/forgot-password" className="text-blue-600 hover:text-blue-700 font-medium text-sm">
            Запросити новий лист
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-emerald-400 mb-4 shadow-xl shadow-blue-500/25">
            <Trophy className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">SportPredict AI</h1>
          <p className="text-slate-400 mt-2">Встановлення нового пароля</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          {success ? (
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-emerald-100 mb-4">
                <KeyRound className="w-7 h-7 text-emerald-600" />
              </div>
              <h2 className="text-xl font-bold text-slate-800 mb-2">Пароль змінено!</h2>
              <p className="text-slate-500 text-sm mb-4">
                Ваш пароль успішно змінено. Зараз вас буде перенаправлено на сторінку входу…
              </p>
              <Link to="/login" className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium text-sm">
                <ArrowLeft className="w-4 h-4" /> Увійти зараз
              </Link>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-bold mb-6 text-center">Новий пароль</h2>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Новий пароль</label>
                  <div className="relative">
                    <input
                      type={showPass ? 'text' : 'password'}
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all pr-12"
                      placeholder="Мінімум 6 символів"
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

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Підтвердіть пароль</label>
                  <input
                    type={showPass ? 'text' : 'password'}
                    value={confirm}
                    onChange={e => setConfirm(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                    placeholder="Повторіть пароль"
                    required
                    minLength={6}
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-xl font-semibold hover:from-blue-700 hover:to-blue-600 transition-all shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <><KeyRound className="w-5 h-5" /> Змінити пароль</>
                  )}
                </button>
              </form>

              <div className="mt-6 text-center">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  <ArrowLeft className="w-4 h-4" /> Повернутися до входу
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
