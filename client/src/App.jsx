import React, { createContext, useContext, useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import OnboardingPage from './pages/OnboardingPage';
import DashboardPage from './pages/DashboardPage';
import AssessmentPage from './pages/AssessmentPage';
import HealthPlanPage from './pages/HealthPlanPage';
import PhysiotherapyPage from './pages/PhysiotherapyPage';
import NutritionPage from './pages/NutritionPage';
import BehaviourPage from './pages/BehaviourPage';
import RecoveryPage from './pages/RecoveryPage';
import ActivityPage from './pages/ActivityPage';
import ProgressPage from './pages/ProgressPage';
import ProfilePage from './pages/ProfilePage';
import ExerciseDetailPage from './pages/ExerciseDetailPage';
import MainLayout from './layouts/MainLayout';

export const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen bg-[#0a0f0a] flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <div className="text-emerald-400 text-sm">Loading MoveWell...</div>
      </div>
    </div>
  );
  if (!user) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('movewell_user');
    const token = localStorage.getItem('movewell_token');
    if (stored && token) {
      try { setUser(JSON.parse(stored)); } catch {}
    }
    setLoading(false);
  }, []);

  const login = (userData, token) => {
    setUser(userData);
    localStorage.setItem('movewell_user', JSON.stringify(userData));
    localStorage.setItem('movewell_token', token);
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('movewell_user');
    localStorage.removeItem('movewell_token');
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={user ? <Navigate to="/dashboard" /> : <LoginPage />} />
          <Route path="/onboarding" element={<ProtectedRoute><OnboardingPage /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><MainLayout><DashboardPage /></MainLayout></ProtectedRoute>} />
          <Route path="/assessment" element={<ProtectedRoute><MainLayout><AssessmentPage /></MainLayout></ProtectedRoute>} />
          <Route path="/plan" element={<ProtectedRoute><MainLayout><HealthPlanPage /></MainLayout></ProtectedRoute>} />
          <Route path="/specialists/physiotherapy" element={<ProtectedRoute><MainLayout><PhysiotherapyPage /></MainLayout></ProtectedRoute>} />
          <Route path="/specialists/nutrition" element={<ProtectedRoute><MainLayout><NutritionPage /></MainLayout></ProtectedRoute>} />
          <Route path="/specialists/behaviour" element={<ProtectedRoute><MainLayout><BehaviourPage /></MainLayout></ProtectedRoute>} />
          <Route path="/specialists/recovery" element={<ProtectedRoute><MainLayout><RecoveryPage /></MainLayout></ProtectedRoute>} />
          <Route path="/specialists/activity" element={<ProtectedRoute><MainLayout><ActivityPage /></MainLayout></ProtectedRoute>} />
          <Route path="/progress" element={<ProtectedRoute><MainLayout><ProgressPage /></MainLayout></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><MainLayout><ProfilePage /></MainLayout></ProtectedRoute>} />
          <Route path="/exercises/:id" element={<ProtectedRoute><MainLayout><ExerciseDetailPage /></MainLayout></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}
