import React, { useEffect, useState } from 'react';
import {
  User, ShieldCheck, CheckCircle, AlertCircle, Save,
  ArrowRight, Heart, Activity
} from 'lucide-react';
import { profileService, workflowService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function ProfilePage() {
  const [profile, setProfile] = useState({});
  const [screening, setScreening] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        const res = await profileService.get();
        if (res.data.profile) setProfile(res.data.profile);
        if (res.data.health_screening) setScreening(res.data.health_screening);
      } catch (err) {
        console.error('Error fetching profile:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);

    try {
      const payload = {
        ...profile,
        ...screening
      };
      await profileService.update(payload);
      // Run workflow so updated profile influences future specialist runs
      await workflowService.run();
      setSavedSuccess(true);
    } catch (err) {
      console.error('Error updating profile:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading Profile &amp; Clinical Context..." />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Title */}
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight">Unified User Wellness Profile</h1>
        <p className="text-sm text-emerald-100/70 mt-1">
          Central source of truth consumed across all six specialist domains. Updating your profile automatically recalibrates your Unified Health Plan.
        </p>
      </div>

      {savedSuccess && (
        <div className="bg-emerald-500/20 border border-emerald-500/40 rounded-xl p-4 text-emerald-300 flex items-center gap-2.5">
          <CheckCircle size={18} className="text-emerald-400" />
          <span className="text-sm font-semibold">
            Profile saved! The wellness workflow has recalibrated your specialist outputs.
          </span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Personal & Biometrics */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <User size={18} className="text-emerald-400" />
            <span>Personal &amp; Anthropometric Biometrics</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Height (cm)</label>
              <input
                type="number"
                value={profile.height || ''}
                onChange={e => setProfile({ ...profile, height: parseFloat(e.target.value) })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Weight (kg)</label>
              <input
                type="number"
                step="0.5"
                value={profile.weight || ''}
                onChange={e => setProfile({ ...profile, weight: parseFloat(e.target.value) })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Work Pattern</label>
              <select
                value={profile.work_pattern || 'OFFICE'}
                onChange={e => setProfile({ ...profile, work_pattern: e.target.value })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              >
                <option value="OFFICE">Office / Desk Seated</option>
                <option value="HYBRID">Hybrid (Standing &amp; Sitting)</option>
                <option value="ACTIVE">Physically Active / Standing</option>
              </select>
            </div>
          </div>
        </div>

        {/* Physical Activity & Sedentary Habituation */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Activity size={18} className="text-emerald-400" />
            <span>Activity Habits &amp; Sedentary Profile</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Daily Step Baseline</label>
              <input
                type="number"
                value={profile.daily_steps || ''}
                onChange={e => setProfile({ ...profile, daily_steps: parseInt(e.target.value) })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Daily Sitting Duration (Hours)</label>
              <input
                type="number"
                step="0.5"
                value={profile.sitting_hours || ''}
                onChange={e => setProfile({ ...profile, sitting_hours: parseFloat(e.target.value) })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Movement Breaks / Day</label>
              <input
                type="number"
                value={profile.movement_breaks || ''}
                onChange={e => setProfile({ ...profile, movement_breaks: parseInt(e.target.value) })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              />
            </div>
          </div>
        </div>

        {/* Clinical Health Screening with YES / NO / UNKNOWN */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-emerald-900/30">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <ShieldCheck size={18} className="text-emerald-400" />
                <span>Clinical Health Screening (Physiotherapy Safety Gate)</span>
              </h2>
              <p className="text-xs text-emerald-100/60 mt-0.5">
                Answers preserve UNKNOWN distinctions to protect safety thresholds.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {[
              { key: 'heart_condition', label: 'Heart or Cardiovascular Condition' },
              { key: 'hypertension', label: 'Hypertension / High Blood Pressure' },
              { key: 'joint_pain', label: 'Persistent Joint or Ligament Pain' },
              { key: 'back_pain', label: 'Chronic Lumbar / Lower Back Pain' },
              { key: 'neck_pain', label: 'Cervical / Neck Stiffness' },
              { key: 'injury_history', label: 'Previous Musculoskeletal Injury' }
            ].map((q) => (
              <div key={q.key} className="flex flex-wrap items-center justify-between p-3 bg-[#111a11] rounded-lg border border-emerald-900/30 gap-2">
                <span className="text-xs font-semibold text-white">{q.label}</span>
                <div className="flex items-center gap-2">
                  {['YES', 'NO', 'UNKNOWN'].map((opt) => (
                    <button
                      type="button"
                      key={opt}
                      onClick={() => setScreening({ ...screening, [q.key]: opt })}
                      className={`text-xs px-3 py-1 rounded font-mono font-bold transition-colors ${
                        screening[q.key] === opt
                          ? opt === 'YES'
                            ? 'bg-amber-500 text-black'
                            : opt === 'NO'
                            ? 'bg-emerald-500 text-black'
                            : 'bg-emerald-900 text-emerald-200'
                          : 'bg-[#0a0f0a] text-emerald-700 hover:text-emerald-400'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Save CTA */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saving}
            className="bg-emerald-500 hover:bg-emerald-600 text-white px-6 py-3 rounded-xl text-sm font-bold transition-all shadow-lg flex items-center gap-2"
          >
            <Save size={16} />
            <span>{saving ? 'Updating System...' : 'Save Profile & Recalibrate'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}

