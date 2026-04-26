import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Trophy, Mail, ArrowLeft } from 'lucide-react';
import api from '../services/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.post('/auth/forgot-password', { email });
      setSent(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка. Спробуйте ще раз.');
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
          <p className="text-slate-400 mt-2">Скидання пароля</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          {sent ? (
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-emerald-100 mb-4">
                <Mail className="w-7 h-7 text-emerald-600" />
              </div>
              <h2 className="text-xl font-bold text-slate-800 mb-2">Лист надіслано</h2>
              <p className="text-slate-500 text-sm mb-6">
                Якщо цей email зареєстрований у системі, ви отримаєте лист із посиланням
                для скидання пароля. Перевірте папку «Спам», якщо лист не з'явився.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium text-sm"
              >
                <ArrowLeft className="w-4 h-4" /> Повернутися до входу
              </Link>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-bold mb-2 text-center">Забули пароль?</h2>
              <p className="text-slate-500 text-sm text-center mb-6">
                Введіть email, пов'язаний з вашим акаунтом, і ми надішлемо посилання для скидання пароля.
              </p>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
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

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-xl font-semibold hover:from-blue-700 hover:to-blue-600 transition-all shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <><Mail className="w-5 h-5" /> Надіслати посилання</>
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
