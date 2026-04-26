import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './components/Toast';
import Layout from './components/Layout';
import './index.css';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const MatchesPage = lazy(() => import('./pages/MatchesPage'));
const MatchDetailPage = lazy(() => import('./pages/MatchDetailPage'));
const TeamsPage = lazy(() => import('./pages/TeamsPage'));
const TeamDetailPage = lazy(() => import('./pages/TeamDetailPage'));
const PredictionsPage = lazy(() => import('./pages/PredictionsPage'));
const AIModelsPage = lazy(() => import('./pages/AIModelsPage'));
const StandingsPage = lazy(() => import('./pages/StandingsPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const SportHubPage = lazy(() => import('./pages/SportHubPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));

function FullScreenSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <FullScreenSpinner />;
  return user ? children : <Navigate to="/login" replace />;
}

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) return <FullScreenSpinner />;

  return (
    <Suspense fallback={<FullScreenSpinner />}>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="matches" element={<MatchesPage />} />
          <Route path="sports-hub" element={<SportHubPage />} />
          <Route path="matches/:id" element={<MatchDetailPage />} />
          <Route path="teams" element={<TeamsPage />} />
          <Route path="teams/:id" element={<TeamDetailPage />} />
          <Route path="predictions" element={<PredictionsPage />} />
          <Route path="ai-models" element={<AIModelsPage />} />
          <Route path="standings" element={<StandingsPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
        <Route path="*" element={<Suspense fallback={<FullScreenSpinner />}><NotFoundPage /></Suspense>} />
      </Routes>
    </Suspense>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
