import React, { useEffect, useState } from 'react';
import {
  Dumbbell, Activity, CheckCircle, Clock, Plus, Flame,
  TrendingUp, AlertCircle, RefreshCw, Footprints, Shield
} from 'lucide-react';
import { activityService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function ActivityPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newActivity, setNewActivity] = useState({
    daily_steps: 8000,
    sitting_hours: 6.0,
    movement_breaks: 5,
    exercise_type: 'Walking',
    exercise_minutes: 30
  });
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const fetchActivity = async () => {
    try {
      setLoading(true);
      const res = await activityService.getAll();
      setData(res.data);
    } catch (err) {
      console.error('Error fetching activity:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActivity();
  }, []);

  const handleLogActivity = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await activityService.log(newActivity);
      setShowModal(false);
      await fetchActivity();
    } catch (err) {
      console.error('Error logging activity:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading Exercise &amp; Activity Protocol from SQLite..." />
      </div>
    );
  }

  const records = data?.records || [];
  const hasRecords = records.length > 0;
  const latest = hasRecords ? records[0] : null;
  const targetSteps = 8000;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Breadcrumb & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 font-mono mb-1">
            <span>My Plan &gt; Exercise &amp; Activity &gt; Daily Kinematic Volume</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-white tracking-tight">Your Activity Plan</h1>
            <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-500/30 font-medium">
              Live Synced
            </span>
          </div>
          <p className="text-sm text-emerald-100/70 mt-1.5 max-w-3xl">
            Non-exercise physical activity, low-impact joint conditioning, and sedentary posture mitigation separate from prescribed physiotherapy exercises.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowModal(!showModal)}
            className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg"
          >
            <Plus size={15} />
            <span>Log Custom Activity</span>
          </button>
        </div>
      </div>

      {/* Distinction Callout Banner */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-4 flex items-center gap-3">
        <Footprints size={20} className="text-emerald-400 flex-shrink-0" />
        <p className="text-xs text-emerald-100/80">
          <strong>Note:</strong> These activities build systemic cardiovascular and joint lubrication capacity. For targeted injury rehabilitation protocols, visit your Physiotherapy Plan.
        </p>
      </div>

      {/* Modal / Log Form */}
      {showModal && (
        <form onSubmit={handleLogActivity} className="bg-[#0f1a0f] border border-emerald-500/40 rounded-xl p-5 space-y-4 shadow-xl">
          <h3 className="text-sm font-bold text-white">Log Today's Movement &amp; Step Volume</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Daily Step Count</label>
              <input
                type="number"
                min="0"
                max="50000"
                value={newActivity.daily_steps}
                onChange={e => setNewActivity({ ...newActivity, daily_steps: parseInt(e.target.value) || 0 })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
                required
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Sitting Hours</label>
              <input
                type="number"
                step="0.5"
                min="0"
                max="24"
                value={newActivity.sitting_hours}
                onChange={e => setNewActivity({ ...newActivity, sitting_hours: parseFloat(e.target.value) || 0 })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
                required
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Movement Breaks Taken</label>
              <input
                type="number"
                min="0"
                max="30"
                value={newActivity.movement_breaks}
                onChange={e => setNewActivity({ ...newActivity, movement_breaks: parseInt(e.target.value) || 0 })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Exercise / Activity Type</label>
              <input
                type="text"
                value={newActivity.exercise_type}
                onChange={e => setNewActivity({ ...newActivity, exercise_type: e.target.value })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-emerald-400 block mb-1">Active Minutes</label>
              <input
                type="number"
                min="0"
                max="300"
                value={newActivity.exercise_minutes}
                onChange={e => setNewActivity({ ...newActivity, exercise_minutes: parseInt(e.target.value) || 0 })}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-2.5 text-white text-sm"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setShowModal(false)}
              className="px-3 py-1.5 text-xs text-emerald-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 text-xs bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium"
            >
              {submitting ? 'Saving to SQLite...' : 'Save Activity'}
            </button>
          </div>
        </form>
      )}

      {/* 4 Key Activity Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Step volume */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Daily Step Volume</span>
          <div className="flex items-baseline gap-2">
            {latest?.daily_steps ? (
              <span className="text-3xl font-bold text-white font-mono">{latest.daily_steps.toLocaleString()}</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
            <span className="text-xs text-emerald-500 font-mono">/ {targetSteps.toLocaleString()}</span>
          </div>
          <p className="text-[11px] text-emerald-400/90 font-mono">
            {latest?.daily_steps
              ? `${Math.round((latest.daily_steps / targetSteps) * 100)}% achieved • ${Math.max(0, targetSteps - latest.daily_steps).toLocaleString()} to target`
              : 'Target: 8,000 steps/day'}
          </p>
        </div>

        {/* Metric 2: Walking Duration */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Active Walking Duration</span>
          <div className="flex items-baseline gap-2">
            {latest?.exercise_minutes ? (
              <span className="text-3xl font-bold text-white font-mono">{latest.exercise_minutes} mins</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Aerobic joint lubrication</p>
        </div>

        {/* Metric 3: Sitting & Inactivity */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Sitting &amp; Inactivity</span>
          <div className="flex items-baseline gap-2">
            {latest?.sitting_hours ? (
              <span className="text-3xl font-bold text-white font-mono">{latest.sitting_hours} hrs</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Sedentary exposure ceiling: 7.0 hrs</p>
        </div>

        {/* Metric 4: Movement Breaks */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Movement Breaks</span>
          <div className="flex items-baseline gap-2">
            {latest?.movement_breaks ? (
              <span className="text-3xl font-bold text-white font-mono">{latest.movement_breaks} / 6 breaks</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-400 font-mono">Micro-breaks during desk intervals</p>
        </div>
      </div>

      {/* Main Grid: Today's Movement Checklist + Weekly Volume */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Movement & Activity Checklist */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
            <div>
              <h3 className="text-base font-bold text-white">Today's Daily Movement &amp; Activity Checklist</h3>
              <p className="text-xs text-emerald-100/60">Habitual micro-dosing of cardiovascular load</p>
            </div>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              Active Checklist
            </span>
          </div>

          <div className="space-y-3">
            {[
              {
                title: 'Morning Commute / Brisk Walk',
                desc: 'Continuous pace, pelvic tilt calibration, arm swing activation.',
                metrics: 'Target: 20 mins continuous walking',
                time: 'Morning'
              },
              {
                title: 'Lunchtime Low-Impact Stroll',
                desc: 'Digestive pacing, solar exposure, lumbar decompression.',
                metrics: 'Target: 15 mins post-meal stroll',
                time: 'Mid-day'
              },
              {
                title: 'Hourly Movement & Posture Reset',
                desc: 'Stand up, walk or stretch for 2 minutes every hour seated.',
                metrics: 'Target: 5+ breaks throughout workday',
                time: 'Afternoon'
              },
              {
                title: 'Evening Mobility & Wind-Down Walk',
                desc: 'Assists postprandial glucose uptake and clears hip flexor congestion.',
                metrics: 'Target: 15-20 mins gentle stroll',
                time: 'Evening'
              }
            ].map((item, i) => (
              <div key={i} className="p-3.5 bg-[#111a11] border border-emerald-900/40 rounded-lg flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white">{item.title}</span>
                    <span className="text-[10px] text-emerald-600 font-mono">{item.time}</span>
                  </div>
                  <p className="text-[11px] text-emerald-100/70">{item.desc}</p>
                  <p className="text-[10px] text-emerald-400 font-mono">{item.metrics}</p>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded font-semibold whitespace-nowrap bg-emerald-500/10 text-emerald-400 border border-emerald-900/40">
                  Scheduled
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Weekly Movement Volume Chart */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
            <div>
              <h3 className="text-base font-bold text-white">Movement Volume Overview</h3>
              <p className="text-xs text-emerald-100/60">Steps logged in SQLite across recent entries</p>
            </div>
            <span className="text-xs font-mono text-emerald-400">{records.length} logged sessions</span>
          </div>

          {!hasRecords ? (
            <div className="h-56 flex flex-col items-center justify-center border border-dashed border-emerald-900/40 rounded-lg text-center p-6 space-y-2">
              <Footprints size={24} className="text-emerald-700" />
              <p className="text-xs text-emerald-100/60">No activity sessions logged yet.</p>
              <button
                onClick={() => setShowModal(true)}
                className="text-xs text-emerald-400 font-semibold underline"
              >
                Log your first activity session →
              </button>
            </div>
          ) : (
            <div className="h-56 flex items-end justify-between gap-3 pt-6 px-2">
              {records.slice(0, 7).reverse().map((d, idx) => (
                <div key={d.id || idx} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                  <span className="text-[9px] font-mono text-emerald-400">
                    {d.daily_steps ? `${(d.daily_steps / 1000).toFixed(1)}k` : '—'}
                  </span>
                  <div
                    style={{ height: `${Math.min(140, ((d.daily_steps || 0) / 12000) * 140)}px` }}
                    className="w-full max-w-[32px] bg-emerald-500 hover:bg-emerald-400 rounded-t transition-all"
                    title={`${d.record_date}: ${(d.daily_steps || 0).toLocaleString()} steps`}
                  />
                  <span className="text-[10px] text-emerald-600 font-mono">
                    {d.record_date ? d.record_date.substring(5) : `D${idx + 1}`}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="p-3 bg-[#111a11] border border-emerald-900/40 rounded-lg text-xs space-y-1">
            <span className="text-emerald-400 font-bold block">Exercise Specialist Guidance</span>
            <p className="text-emerald-100/70 text-[11px]">
              Continuous physical activity mitigates musculoskeletal stiffness and promotes neuro-motor recovery without overloading joint cartilage.
            </p>
          </div>
        </div>
      </div>

      {/* Completed Activity History Table */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
          <div>
            <h3 className="text-base font-bold text-white">Completed Activity History</h3>
            <p className="text-xs text-emerald-100/60">Chronological activity telemetry feed from SQLite</p>
          </div>
          <span className="text-xs text-emerald-400 font-mono">{records.length} records</span>
        </div>

        {!hasRecords ? (
          <div className="py-8 text-center border border-dashed border-emerald-900/40 rounded-lg text-xs text-emerald-100/60 space-y-2">
            <p>No activity logs found in database.</p>
            <button
              onClick={() => setShowModal(true)}
              className="text-emerald-400 font-semibold underline block mx-auto"
            >
              Log your steps and activity for today →
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-emerald-700 border-b border-emerald-900/40">
                  <th className="pb-2">Date</th>
                  <th className="pb-2">Daily Steps</th>
                  <th className="pb-2">Sitting Hours</th>
                  <th className="pb-2">Movement Breaks</th>
                  <th className="pb-2">Exercise Recorded</th>
                  <th className="pb-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-emerald-900/20 text-emerald-100/80">
                {records.slice(0, 10).map((r, idx) => (
                  <tr key={r.id || idx} className="hover:bg-white/[0.02]">
                    <td className="py-3 text-white font-semibold">{r.record_date}</td>
                    <td className="py-3 text-emerald-400 font-bold">{r.daily_steps ? r.daily_steps.toLocaleString() : '—'} steps</td>
                    <td className="py-3">{r.sitting_hours ? `${r.sitting_hours} hrs` : '—'}</td>
                    <td className="py-3">{r.movement_breaks ? `${r.movement_breaks} breaks` : '—'}</td>
                    <td className="py-3 text-emerald-100/70">{r.exercise_type || 'Walking'} ({r.exercise_minutes || 0}m)</td>
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
    </div>
  );
}
