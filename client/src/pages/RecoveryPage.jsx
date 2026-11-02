import React, { useEffect, useState } from 'react';
import {
  Moon, Heart, Activity, CheckCircle, Clock, ShieldCheck,
  Plus, AlertCircle, Sparkles, RefreshCw, Mic
} from 'lucide-react';
import { recoveryService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import RecoveryVoiceAgentModal from '../components/recovery/RecoveryVoiceAgentModal';

export default function RecoveryPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newLog, setNewLog] = useState({
    sleep_duration: 7.5,
    sleep_quality: 'GOOD',
    stress_level: 3,
    recovery_notes: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showVoiceModal, setShowVoiceModal] = useState(false);

  const fetchRecovery = async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);
      const res = await recoveryService.getAll();
      setData(res.data);
    } catch (err) {
      console.error('Error fetching recovery data:', err);
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecovery();
  }, []);

  const handleLogSleep = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await recoveryService.log(newLog);
      setShowForm(false);
      await fetchRecovery();
    } catch (err) {
      console.error('Error logging sleep:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading Wellness &amp; Recovery Protocol from SQLite..." />
      </div>
    );
  }

  const records = data?.records || [];
  const profile = data?.profile || {};
  const hasRecords = records.length > 0;
  const latest = hasRecords ? records[0] : null;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Breadcrumb & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 font-mono mb-1">
            <span>My Plan &gt; Wellness &amp; Recovery &gt; Rest, Recovery &amp; Sleep</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Your Recovery Plan</h1>
          <p className="text-sm text-emerald-100/70 mt-1.5 max-w-3xl">
            Sleep tracking, evening wind-down routines, and simple relaxation practices to help your body recover and feel refreshed.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowVoiceModal(true)}
            className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white px-4 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-emerald-950/60 ring-1 ring-emerald-400/40 hover:scale-[1.02]"
          >
            <Mic size={16} className="text-emerald-200 animate-pulse" />
            <span>Talk to Recovery Coach (AI Voice)</span>
          </button>

          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 bg-[#132213] hover:bg-emerald-900/40 text-emerald-200 border border-emerald-800/60 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
          >
            <Plus size={15} />
            <span>Manual Form Log</span>
          </button>
        </div>
      </div>

      {/* AI Voice Agent Hero Banner */}
      <div className="bg-gradient-to-r from-[#0c1a0c] via-[#0f210f] to-[#0a150a] border border-emerald-500/40 rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl ring-1 ring-emerald-500/20">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-300 shrink-0 shadow-inner">
            <Sparkles size={24} className="animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">Interactive Voice Recovery Specialist</h2>
              <span className="text-[10px] bg-emerald-500/20 text-emerald-300 font-mono px-2 py-0.5 rounded-full border border-emerald-500/30">
                GPT-4o Mini (OpenRouter)
              </span>
            </div>
            <p className="text-xs text-emerald-100/75 mt-1 max-w-xl">
              Talk freely or ask questions about sleep, fatigue, and stress. The agent automatically writes your check-in records to SQLite in the background and updates your MoveWell score instantly.
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowVoiceModal(true)}
          className="shrink-0 flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-black font-semibold px-4 py-2.5 rounded-xl text-xs transition-all shadow-lg hover:shadow-emerald-500/20 hover:scale-[1.02]"
        >
          <Mic size={14} />
          <span>Open Voice Check-In</span>
          <span className="text-xs font-mono">→</span>
        </button>
      </div>

      {/* Log Form modal/card */}
      {showForm && (
        <form onSubmit={handleLogSleep} className="bg-[#0f1a0f] border border-emerald-500/40 rounded-xl p-5 space-y-4 shadow-xl">
          <h3 className="text-sm font-bold text-white">Manual Sleep &amp; Recovery Form</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Sleep Duration (Hours)</label>
              <input
                type="number"
                step="0.1"
                min="3"
                max="14"
                value={newLog.sleep_duration}
                onChange={e => setNewLog({ ...newLog, sleep_duration: parseFloat(e.target.value) })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm focus:border-emerald-500"
                required
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Sleep Quality</label>
              <select
                value={newLog.sleep_quality}
                onChange={e => setNewLog({ ...newLog, sleep_quality: e.target.value })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm focus:border-emerald-500"
              >
                <option value="EXCELLENT">Excellent</option>
                <option value="GOOD">Good</option>
                <option value="FAIR">Fair</option>
                <option value="POOR">Poor</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Stress Level (1-10)</label>
              <input
                type="number"
                min="1"
                max="10"
                value={newLog.stress_level}
                onChange={e => setNewLog({ ...newLog, stress_level: parseInt(e.target.value) })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm focus:border-emerald-500"
                required
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-emerald-400 block mb-1">Recovery Notes (Symptoms, Soreness)</label>
            <input
              type="text"
              placeholder="e.g. Mild shoulder tightness upon waking; fully resolved after warm-up"
              value={newLog.recovery_notes}
              onChange={e => setNewLog({ ...newLog, recovery_notes: e.target.value })}
              className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm focus:border-emerald-500"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-3 py-1.5 text-xs text-emerald-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium"
            >
              {submitting ? 'Saving to SQLite...' : 'Save Check-in'}
            </button>
          </div>
        </form>
      )}

      {/* 4 Key Recovery Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Sleep Duration */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Sleep Duration</span>
          <div className="flex items-baseline gap-2">
            {latest ? (
              <span className="text-3xl font-bold text-white font-mono">{latest.sleep_duration} hrs</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-400/90 font-mono">
            {latest ? `Logged on ${latest.record_date}` : 'No recovery check-in recorded'}
          </p>
        </div>

        {/* Metric 2: Sleep Quality */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Sleep Efficiency &amp; Quality</span>
          <div className="flex items-baseline gap-2">
            {latest ? (
              <>
                <span className="text-2xl font-bold text-white font-mono capitalize">{latest.sleep_quality}</span>
                <span className="text-xs text-emerald-400 font-semibold uppercase">Restorative</span>
              </>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Circadian restoration profile</p>
        </div>

        {/* Metric 3: Stress Score */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Autonomic Stress Index</span>
          <div className="flex items-baseline gap-2">
            {latest ? (
              <>
                <span className="text-3xl font-bold text-white font-mono">{latest.stress_level * 10}</span>
                <span className="text-xs text-emerald-500 font-mono">/ 100</span>
                <span className="text-xs text-emerald-400 font-semibold">
                  {latest.stress_level <= 3 ? 'Low' : latest.stress_level <= 6 ? 'Moderate' : 'Elevated'}
                </span>
              </>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Parasympathetic equilibrium</p>
        </div>

        {/* Metric 4: Subjective Strain */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Subjective Recovery Strain</span>
          <div className="flex items-baseline gap-2">
            {latest ? (
              <>
                <span className="text-3xl font-bold text-white font-mono">{latest.stress_level} / 10</span>
                <span className="text-xs text-emerald-400 font-semibold">
                  {latest.stress_level <= 3 ? 'Mild' : 'Active'}
                </span>
              </>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Self-reported recovery state</p>
        </div>
      </div>

      {/* Main Grid: Checklist + Weekly Sleep Trends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Recovery Actions & Protocol Checklist */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
            <div>
              <h3 className="text-base font-bold text-white">Daily Recovery Actions &amp; Protocol</h3>
              <p className="text-xs text-emerald-100/60">Scheduled clinical habits to downregulate sympathetic tone</p>
            </div>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              Active Routine
            </span>
          </div>

          <div className="space-y-3">
            {[
              {
                title: 'Evening Magnesium & Hydration Protocol',
                desc: 'Nutritional support for muscle micro-tear reduction and sleep onset induction.',
                time: '10:00 PM',
                status: 'Scheduled'
              },
              {
                title: '10-Minute Dark-Room Parasympathetic Breathwork (4-7-8 Breathing)',
                desc: 'Vagal nerve stimulation to lower resting heart rate prior to sleep onset.',
                time: '10:15 PM',
                status: 'Scheduled'
              },
              {
                title: 'Mid-Day Contrast Warm Hydrotherapy or Targeted Foam Rolling',
                desc: 'Targets myofascial tissue tension around thoracic spine and glute medius.',
                time: '2:30 PM',
                status: 'Scheduled'
              },
              {
                title: 'Evening Blue-Light Filter & Circadian Dimming',
                desc: 'Melatonin protection phase (T-60 min before planned sleep window).',
                time: '9:30 PM',
                status: 'Scheduled'
              }
            ].map((action, i) => (
              <div
                key={i}
                className="p-3.5 bg-[#111a11] border border-emerald-900/40 rounded-lg flex items-start justify-between gap-3"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white">{action.title}</span>
                    <span className="text-[10px] text-emerald-600 font-mono">{action.time}</span>
                  </div>
                  <p className="text-[11px] text-emerald-100/70">{action.desc}</p>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded font-semibold whitespace-nowrap bg-emerald-500/10 text-emerald-400 border border-emerald-900/40">
                  {action.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Weekly Sleep & Recovery Trends Chart */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
            <div>
              <h3 className="text-base font-bold text-white">Weekly Sleep &amp; Recovery Trends</h3>
              <p className="text-xs text-emerald-100/60">Sleep duration logged across recent days</p>
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono text-emerald-400">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                Target (7-9 hrs)
              </span>
            </div>
          </div>

          {/* Bar representation */}
          <div className="h-44 flex items-end justify-between gap-2 pt-4 px-2">
            {(records.length > 0 ? records.slice(0, 7).reverse() : [
              { record_date: 'Day 1', sleep_duration: 7.2 },
              { record_date: 'Day 2', sleep_duration: 8.0 },
              { record_date: 'Day 3', sleep_duration: 6.8 },
              { record_date: 'Day 4', sleep_duration: 7.5 },
              { record_date: 'Day 5', sleep_duration: 8.2 },
              { record_date: 'Day 6', sleep_duration: 7.0 },
              { record_date: 'Day 7', sleep_duration: latest?.sleep_duration || 7.5 }
            ]).map((d, i) => {
              const dur = d.sleep_duration || 0;
              const heightPct = Math.min(100, Math.round((dur / 10) * 100));
              const isTarget = dur >= 7.0;
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end group">
                  <div className="text-[10px] text-emerald-400 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
                    {dur}h
                  </div>
                  <div
                    style={{ height: `${heightPct}%` }}
                    className={`w-full max-w-[36px] rounded-t transition-all duration-300 ${
                      isTarget
                        ? 'bg-gradient-to-t from-emerald-600 to-emerald-400 shadow-lg shadow-emerald-900/40'
                        : 'bg-gradient-to-t from-amber-700 to-amber-500'
                    }`}
                  />
                  <span className="text-[9px] text-emerald-600 font-mono truncate max-w-[40px]">
                    {d.record_date ? d.record_date.slice(5) : `D${i + 1}`}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="pt-2 border-t border-emerald-900/20 flex items-center justify-between text-[11px] text-emerald-400/80 font-mono">
            <span>Minimum 7.0h recommended</span>
            <span>Target: 7.5–8.5h</span>
          </div>
        </div>
      </div>

      {/* Sleep Log History Table */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
          <div>
            <h3 className="text-base font-bold text-white">Sleep &amp; Recovery Audit Log</h3>
            <p className="text-xs text-emerald-100/60">Historical entries recorded in SQLite</p>
          </div>
          <span className="text-xs text-emerald-400 font-mono">{records.length} records logged</span>
        </div>

        {!hasRecords ? (
          <div className="py-8 text-center border border-dashed border-emerald-900/40 rounded-lg text-xs text-emerald-100/60 space-y-2">
            <p>No recovery check-in logs found in SQLite.</p>
            <button
              onClick={() => setShowVoiceModal(true)}
              className="text-emerald-400 font-semibold underline block mx-auto"
            >
              Start voice check-in today →
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-emerald-700 border-b border-emerald-900/40">
                  <th className="pb-2">Date</th>
                  <th className="pb-2">Sleep Duration</th>
                  <th className="pb-2">Perceived Strain</th>
                  <th className="pb-2">Notes &amp; Sensations</th>
                  <th className="pb-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-emerald-900/20 text-emerald-100/80">
                {records.slice(0, 10).map((rec, i) => (
                  <tr key={rec.id || i} className="hover:bg-white/[0.02]">
                    <td className="py-3 text-white font-semibold">{rec.record_date}</td>
                    <td className="py-3 text-emerald-300">{rec.sleep_duration} hrs ({rec.sleep_quality})</td>
                    <td className="py-3 text-amber-400">+{rec.stress_level} / 10 Strain</td>
                    <td className="py-3 text-emerald-100/70">{rec.recovery_notes || 'Restorative sleep logged'}</td>
                    <td className="py-3 text-right">
                      <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/30">
                        Saved in DB
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Voice Agent Modal */}
      <RecoveryVoiceAgentModal
        isOpen={showVoiceModal}
        onClose={() => setShowVoiceModal(false)}
        onRecordLogged={() => fetchRecovery(true)}
      />
    </div>
  );
}
