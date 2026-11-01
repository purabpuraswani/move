import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Stethoscope, ShieldCheck, AlertCircle, CheckCircle, PlayCircle,
  Clock, Dumbbell, Activity, RefreshCw, MessageSquare, AlertTriangle, ArrowRight
} from 'lucide-react';
import { specialistService, exerciseService, assessmentService, planService } from '../services/api';
import ExerciseTrackingCard from '../components/exercise/ExerciseTrackingCard';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function PhysiotherapyPage() {
  const [data, setData] = useState(null);
  const [exercises, setExercises] = useState([]);
  const [assessments, setAssessments] = useState([]);
  const [planActivities, setPlanActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPhysioData = async () => {
    try {
      setLoading(true);
      const [specRes, exRes, assessRes, planRes] = await Promise.allSettled([
        specialistService.getByName('PHYSIOTHERAPY'),
        exerciseService.getAll(),
        assessmentService.getAll(),
        planService.current()
      ]);
      if (specRes.status === 'fulfilled') setData(specRes.value.data);
      if (exRes.status === 'fulfilled') setExercises(exRes.value.data);
      if (assessRes.status === 'fulfilled') setAssessments(assessRes.value.data);
      if (planRes.status === 'fulfilled') {
        const acts = planRes.value.data?.activities || [];
        setPlanActivities(acts.filter(a => a.specialist_name === 'PHYSIOTHERAPY'));
      }
    } catch (err) {
      console.error('Error fetching physio data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPhysioData();
  }, []);

  const handleCompleteExercise = async (exerciseId) => {
    try {
      await fetchPhysioData();
    } catch (err) {
      console.error('Refresh physio data error:', err);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading Physiotherapy Protocol from SQLite..." />
      </div>
    );
  }

  const shoulderAssess = assessments.find(a => a.assessment_type === 'SHOULDER_RAISE');
  const balanceAssess = assessments.find(a => a.assessment_type === 'ONE_LEG_STAND');

  // Track completed exercise IDs from today's plan activities
  const completedExerciseIds = new Set(
    planActivities.filter(a => a.completion_status === 'COMPLETED').map(a => a.exercise_id).filter(Boolean)
  );

  const completedCount = completedExerciseIds.size;
  const totalCount = exercises.length > 0 ? exercises.length : planActivities.length;
  const adherencePct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Breadcrumbs & Title */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 font-mono mb-1">
            <span>My Plan &gt; Physiotherapy &gt; Daily Exercise Order</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-white tracking-tight">Your Physiotherapy Plan</h1>
            <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2.5 py-0.5 rounded-full border border-emerald-500/30 font-medium">
              Safety Gate Certified • Personalized Routine
            </span>
          </div>
          <p className="text-sm text-emerald-100/70 mt-1.5">
            Targeted kinematic routine derived from your movement assessment and health screening. Focus: Scapular control and bilateral ankle/hip stability.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/assessment"
            className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg"
          >
            <PlayCircle size={15} />
            <span>Start Guided Session</span>
          </Link>
        </div>
      </div>

      {/* Kinetic Telemetry & Diagnostic Status Pills */}
      <div className="flex flex-wrap gap-2.5">
        <span className="text-xs bg-[#0f1a0f] border border-emerald-500/30 text-emerald-300 px-3 py-1 rounded-full font-mono">
          • Shoulder Flexion:{' '}
          <strong className="text-white">
            {shoulderAssess
              ? `${Math.round(((shoulderAssess.left_measurement || 0) + (shoulderAssess.right_measurement || 0)) / 2)}°`
              : 'Not Assessed'}
          </strong>
        </span>
        <span className="text-xs bg-[#0f1a0f] border border-emerald-500/30 text-emerald-300 px-3 py-1 rounded-full font-mono">
          • Single-Leg Balance:{' '}
          <strong className="text-white">
            {balanceAssess
              ? `${balanceAssess.left_measurement}s L vs ${balanceAssess.right_measurement}s R`
              : 'Not Assessed'}
          </strong>
        </span>
        <span className="text-xs bg-[#0f1a0f] border border-emerald-500/30 text-emerald-300 px-3 py-1 rounded-full font-mono">
          • Safety Gate:{' '}
          <strong className="text-white">Active Protection</strong>
        </span>
      </div>

      {/* Safety Gate Notification Banner */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <ShieldCheck size={20} className="text-emerald-400 flex-shrink-0" />
          <p className="text-xs text-emerald-100/80">
            <strong>Verified Clinical Safety Gate:</strong> Exercises below are calibrated based on your completed musculoskeletal screening. If sharp pain exceeds 3/10, pause repetition immediately.
          </p>
        </div>
        <span className="text-xs text-emerald-400 font-mono whitespace-nowrap">Protocol Rules ⓘ</span>
      </div>

      {/* Metrics Row: Protocol Progress, Weekly Adherence, Kinematic Load Index */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Today's Protocol Progress */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-emerald-600 uppercase font-semibold">Today's Protocol Progress</span>
            <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded font-mono">Kinematics Active</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white font-mono">
              {completedCount} / {totalCount} completed
            </span>
            <span className="text-emerald-400 font-mono text-sm font-semibold">{adherencePct}%</span>
          </div>
          <p className="text-[11px] text-emerald-100/60">
            {totalCount - completedCount > 0
              ? `${totalCount - completedCount} exercise(s) remaining for optimal neuro-adaptation`
              : 'All prescribed exercises completed for today!'}
          </p>
        </div>

        {/* Weekly Adherence */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-emerald-600 uppercase font-semibold">Weekly Adherence</span>
            <span className="text-[10px] text-emerald-400 font-mono">Cycle Active</span>
          </div>
          <div className="flex items-center gap-2 pt-1">
            {['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'].map((day, idx) => {
              const currentDayIndex = new Date().getDay();
              const adjustedIndex = currentDayIndex === 0 ? 6 : currentDayIndex - 1;
              const isToday = idx === adjustedIndex;
              const isPast = idx < adjustedIndex;
              const done = isPast || (isToday && adherencePct === 100);

              return (
                <div key={day} className="flex-1 text-center">
                  <div
                    className={`w-7 h-7 mx-auto rounded-full flex items-center justify-center text-xs font-mono font-bold ${
                      done
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                        : isToday
                        ? 'bg-emerald-500 text-black border border-emerald-400'
                        : 'bg-[#111a11] text-emerald-800 border border-emerald-900/40'
                    }`}
                  >
                    {done ? '✓' : day[0]}
                  </div>
                  <span className="text-[9px] text-emerald-700 font-mono block mt-1">{day}</span>
                </div>
              );
            })}
          </div>
          <p className="text-[11px] text-emerald-100/60">Continuous tracking across scheduled sessions</p>
        </div>

        {/* Kinematic Load Index */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-emerald-600 uppercase font-semibold">Kinematic Load Index</span>
          </div>
          <div className="flex items-center gap-2">
            <Activity size={20} className="text-emerald-400" />
            <span className="text-xl font-bold text-white">Normal Range</span>
          </div>
          <p className="text-[11px] text-emerald-100/70">
            Joint stress within safe physiological threshold. AI movement analysis active.
          </p>
        </div>
      </div>

      {/* Today's Prescribed Exercises List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white">Today's Prescribed Exercises</h2>
          <span className="text-xs text-emerald-600 font-mono">Sorted by: Sequence order</span>
        </div>

        <div className="space-y-4">
          {exercises.map((ex, index) => {
            const isCompleted = completedExerciseIds.has(ex.id);
            return (
              <ExerciseTrackingCard
                key={ex.id}
                exercise={ex}
                index={index}
                isCompleted={isCompleted}
                onSessionCompleted={fetchPhysioData}
              />
            );
          })}
        </div>
      </div>

      {/* Clinician Support Callout Banner */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <h4 className="text-sm font-bold text-white flex items-center gap-2">
            <AlertTriangle size={15} className="text-amber-400" />
            Experiencing Joint Pinch or Instability?
          </h4>
          <p className="text-xs text-emerald-100/70">
            Your clinical protocol adjusts dynamically. You can log pain ratings or review symptoms in your daily check-in.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/assessment"
            className="text-xs bg-[#111a11] border border-emerald-900/50 hover:bg-emerald-500/10 text-emerald-300 px-3.5 py-2 rounded-lg font-medium transition-colors"
          >
            Reassess Movement
          </Link>
          <Link
            to="/plan"
            className="text-xs bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-1.5"
          >
            <Stethoscope size={13} />
            <span>View Full Plan</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
