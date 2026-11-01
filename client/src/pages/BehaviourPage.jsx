import React, { useEffect, useState } from 'react';
import {
  Brain, CheckCircle, Clock, ShieldCheck, Flame, Plus,
  AlertCircle, Sparkles, RefreshCw
} from 'lucide-react';
import { behaviourService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function BehaviourPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchBehaviour = async () => {
    try {
      setLoading(true);
      const res = await behaviourService.getAll();
      setData(res.data);
    } catch (err) {
      console.error('Error fetching behaviour:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBehaviour();
  }, []);

  const handleToggleHabit = async (habitKey, habitName, currentStatus) => {
    const nextStatus = currentStatus === 'COMPLETED' ? 'SKIPPED' : 'COMPLETED';
    try {
      await behaviourService.log({
        habit_key: habitKey,
        habit_name: habitName,
        status: nextStatus
      });
      await fetchBehaviour();
    } catch (err) {
      console.error('Toggle habit error:', err);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading Behavioural &amp; Habit Protocol from SQLite..." />
      </div>
    );
  }

  const records = data?.records || [];
  const profile = data?.profile || {};

  const habitsList = [
    { key: 'morning_walk', name: 'Morning Walk (20 mins)', time: '8:00 AM', desc: 'Step count baseline and cortisol reset.' },
    { key: 'water_intake', name: 'Drink Water (2.0L+ Target)', time: 'All Day', desc: 'Hydration tracking across scheduled intervals.' },
    { key: 'movement_breaks', name: 'Hourly Movement Break', time: 'Every 50m', desc: 'Stand up, walk or stretch for 2 mins.' },
    { key: 'evening_wind_down', name: 'Evening Wind-Down (No Screens)', time: '9:30 PM', desc: 'Dim lights 30 mins before sleep.' }
  ];

  const completedHabitsCount = records.filter(r => r.status === 'COMPLETED').length;
  const habitStreak = records.length > 0 ? new Set(records.map(r => r.record_date)).size : 0;
  const compliancePct = records.length > 0 ? Math.round((completedHabitsCount / records.length) * 100) : 0;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Breadcrumb & Title */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 font-mono mb-1">
            <span>My Plan &gt; Behaviour &gt; Ergonomic Habituation</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Your Behaviour Plan</h1>
          <p className="text-sm text-emerald-100/70 mt-1.5 max-w-3xl">
            Behavioral habit formation designed to mitigate prolonged sedentary postures, embed automated movement breaks, and reinforce lifestyle consistency.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs bg-emerald-500/20 text-emerald-300 px-3 py-1.5 rounded-lg border border-emerald-500/30 font-mono font-bold flex items-center gap-1.5">
            <Flame size={14} className="text-emerald-400" />
            <span>{habitStreak > 0 ? `${habitStreak}-Day Consistency Streak` : 'Streak Starting Today'}</span>
          </span>
        </div>
      </div>

      {/* 4 Key Behaviour Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Streak */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Active Streak</span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white font-mono">{habitStreak} Days</span>
          </div>
          <p className="text-[11px] text-emerald-400 font-mono">
            {habitStreak > 0 ? 'Consistent desk-break adherence' : 'Complete a habit to begin streak'}
          </p>
        </div>

        {/* Metric 2: Compliance */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Break Compliance</span>
          <div className="flex items-baseline gap-2">
            {records.length > 0 ? (
              <span className="text-3xl font-bold text-white font-mono">{compliancePct}%</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">
            {records.length > 0 ? `${completedHabitsCount} of ${records.length} habits completed` : 'Awaiting daily completions'}
          </p>
        </div>

        {/* Metric 3: Sedentary Exposure */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Sedentary Exposure</span>
          <div className="flex items-baseline gap-2">
            {profile.sitting_hours ? (
              <span className="text-3xl font-bold text-white font-mono">{profile.sitting_hours} hrs</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT SET</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-400 font-mono">
            {profile.sitting_hours ? 'Baseline sitting hours/day' : 'Profile sitting hours unknown'}
          </p>
        </div>

        {/* Metric 4: Primary Motivation */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Primary Goal / Focus</span>
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-bold text-emerald-300 truncate">
              {profile.wellness_goals ? (Array.isArray(profile.wellness_goals) ? profile.wellness_goals[0] : profile.wellness_goals) : 'Postural Restoration'}
            </span>
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">Energy &amp; spinal ergonomics</p>
        </div>
      </div>

      {/* Daily Habits Interactive Checklist */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
          <div>
            <h3 className="text-base font-bold text-white">Daily Habit Checklist</h3>
            <p className="text-xs text-emerald-100/60">Click any habit to log or toggle completion status in SQLite</p>
          </div>
          <span className="text-xs font-mono text-emerald-400">Persistent database state</span>
        </div>

        <div className="space-y-3">
          {habitsList.map((habit) => {
            const todayStr = new Date().toISOString().substring(0, 10);
            const todayRec = records.find(r => r.habit_key === habit.key && r.record_date === todayStr);
            const isCompleted = todayRec?.status === 'COMPLETED';

            return (
              <div
                key={habit.key}
                onClick={() => handleToggleHabit(habit.key, habit.name, isCompleted ? 'COMPLETED' : 'SKIPPED')}
                className={`p-4 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-4 ${
                  isCompleted
                    ? 'bg-[#111a11] border-emerald-500/40 shadow-sm'
                    : 'bg-[#0a0f0a] border-emerald-900/30 opacity-70 hover:opacity-100'
                }`}
              >
                <div className="flex items-center gap-3.5">
                  <div
                    className={`w-6 h-6 rounded flex items-center justify-center border transition-colors ${
                      isCompleted
                        ? 'bg-emerald-500 border-emerald-500 text-black font-bold'
                        : 'border-emerald-700 hover:border-emerald-400'
                    }`}
                  >
                    {isCompleted && <CheckCircle size={15} className="stroke-[3]" />}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-semibold ${isCompleted ? 'text-white' : 'text-emerald-100/60'}`}>
                        {habit.name}
                      </span>
                      <span className="text-[10px] text-emerald-600 font-mono">{habit.time}</span>
                    </div>
                    <p className="text-xs text-emerald-100/70 mt-0.5">{habit.desc}</p>
                  </div>
                </div>

                <span
                  className={`text-xs font-mono px-2.5 py-1 rounded font-bold ${
                    isCompleted
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : 'bg-emerald-950 text-emerald-700 border border-emerald-900/40'
                  }`}
                >
                  {isCompleted ? 'COMPLETED' : 'PENDING'}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
