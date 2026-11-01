import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Heart, Mail, Lock, User, Eye, EyeOff, ArrowRight, Activity } from 'lucide-react';
import { useAuth } from '../App';
import { authService } from '../services/api';

export default function LoginPage() {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      let res;
      if (mode === 'login') {
        res = await authService.login(form.email, form.password);
      } else {
        res = await authService.register(form.name, form.email, form.password);
      }
      const { user, token } = res.data;
      login(user, token);
      navigate(user.onboarding_completed ? '/dashboard' : '/onboarding');
    } catch (err) {
      setError(err.response?.data?.error || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await authService.login('demo@movewell.ai', 'Demo1234!');
      const { user, token } = res.data;
      login(user, token);
      navigate('/dashboard');
    } catch (err) {
      setError('Demo account not available. Please run the backend seed script first.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0f0a] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Ambient background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-emerald-600/5 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-emerald-900/10 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl mb-4">
            <Heart size={28} className="text-emerald-400" />
          </div>
          <h1 className="text-3xl font-bold text-white">MoveWell AI</h1>
          <p className="text-emerald-400/70 mt-1 text-sm">Your intelligent wellness companion</p>
        </div>

        {/* Card */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-2xl p-8 shadow-2xl">
          {/* Toggle */}
          <div className="flex bg-[#0a0f0a] rounded-lg p-1 mb-6">
            <button
              onClick={() => { setMode('login'); setError(''); }}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === 'login' ? 'bg-emerald-500 text-white shadow-lg' : 'text-emerald-400/60 hover:text-emerald-400'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode('register'); setError(''); }}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === 'register' ? 'bg-emerald-500 text-white shadow-lg' : 'text-emerald-400/60 hover:text-emerald-400'
              }`}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-xs text-emerald-400/70 mb-1.5">Full Name</label>
                <div className="relative">
                  <User size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-600" />
                  <input
                    type="text"
                    value={form.name}
                    onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                    className="w-full bg-[#0a0f0a] border border-emerald-900/40 rounded-lg pl-9 pr-4 py-2.5 text-white text-sm focus:outline-none focus:border-emerald-500/60 placeholder-emerald-900 transition-colors"
                    placeholder="Alex Chen"
                    required
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs text-emerald-400/70 mb-1.5">Email</label>
              <div className="relative">
                <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-600" />
                <input
                  type="email"
                  value={form.email}
                  onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
                  className="w-full bg-[#0a0f0a] border border-emerald-900/40 rounded-lg pl-9 pr-4 py-2.5 text-white text-sm focus:outline-none focus:border-emerald-500/60 placeholder-emerald-900 transition-colors"
                  placeholder="you@example.com"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-emerald-400/70 mb-1.5">Password</label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-600" />
                <input
                  type={showPass ? 'text' : 'password'}
                  value={form.password}
                  onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                  className="w-full bg-[#0a0f0a] border border-emerald-900/40 rounded-lg pl-9 pr-10 py-2.5 text-white text-sm focus:outline-none focus:border-emerald-500/60 placeholder-emerald-900 transition-colors"
                  placeholder="••••••••"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPass(p => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-emerald-600 hover:text-emerald-400 transition-colors"
                >
                  {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors shadow-lg"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Please wait...
                </>
              ) : (
                <>
                  {mode === 'login' ? 'Sign In' : 'Create Account'}
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </form>

          {/* Demo */}
          <div className="mt-4 pt-4 border-t border-emerald-900/30">
            <button
              onClick={handleDemo}
              disabled={loading}
              className="w-full border border-emerald-500/30 hover:bg-emerald-500/10 disabled:opacity-50 text-emerald-400 rounded-lg py-2.5 text-sm flex items-center justify-center gap-2 transition-colors"
            >
              <Activity size={14} />
              Try Demo Account
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-emerald-900/60 mt-6">
          MoveWell AI — Intelligent Wellness Management
        </p>
      </div>
    </div>
  );
}
