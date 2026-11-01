import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Clipboard, Stethoscope, Apple, Brain, Moon, Dumbbell, TrendingUp,
  CheckCircle, PlayCircle, Clock, ShieldCheck, AlertTriangle, RefreshCw,
  Sliders, Download, ArrowRight, Activity
} from 'lucide-react';
import { planService, workflowService } from '../services/api';
import ScoreRing from '../components/common/ScoreRing';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function HealthPlanPage() {
  const [planData, setPlanData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const fetchPlan = async () => {
    try {
      setLoading(true);
      const res = await planService.current();
      setPlanData(res.data);
    } catch (err) {
      console.error('Error fetching plan:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlan();
  }, []);

  const handleRunWorkflow = async () => {
    setRunning(true);
    try {
      await workflowService.run();
      await fetchPlan();
    } catch (err) {
      console.error('Workflow run error:', err);
    } finally {
      setRunning(false);
    }
  };

  const handleCompleteActivity = async (activityId) => {
    try {
      await planService.completeActivity(activityId, 'Completed via Plan');
      await fetchPlan();
    } catch (err) {
      console.error('Complete activity error:', err);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading your MoveWell unified plan..." />
      </div>
    );
  }

  const plan = planData?.plan;
  const activities = planData?.activities || [];
  const recommendations = planData?.recommendations || [];
  const specialistsList = planData?.specialists || [];
  const assessments = planData?.assessments || [];
  const screening = planData?.screening || {};

  // Specialist execution lookup map
  const specialistMap = {};
  for (const s of specialistsList) {
    try {
      specialistMap[s.specialist_name] = typeof s.output_json === 'string' ? JSON.parse(s.output_json) : s.output_json;
    } catch {
      specialistMap[s.specialist_name] = {};
    }
  }

  const shoulderAssess = assessments.find(a => a.assessment_type === 'SHOULDER_RAISE');
  const balanceAssess = assessments.find(a => a.assessment_type === 'ONE_LEG_STAND');

  const completedActivities = activities.filter(a => a.completion_status === 'COMPLETED');
  const adherencePct = activities.length > 0 ? Math.round((completedActivities.length / activities.length) * 100) : 0;

  // Check safety gate status
  const hasSafetyFlag = screening.joint_pain === 'YES' || screening.back_pain === 'YES' || screening.heart_condition === 'YES';

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Subheader breadcrumbs & actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 font-mono mb-1">
            <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20 font-sans font-semibold">
              Block A • Active Clinical Protocol
            </span>
            <span>ID: MW-{plan?.id ? plan.id.substring(0, 6).toUpperCase() : '8431'}</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Your MoveWell Plan</h1>
          <p className="text-sm text-emerald-100/60 mt-1">
            Personalized multidisciplinary plan tailored from your movement assessment and clinical health screening.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRunWorkflow}
            disabled={running}
            className="flex items-center gap-2 bg-[#0f1a0f] border border-emerald-500/30 hover:bg-emerald-500/10 text-emerald-300 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <RefreshCw size={14} className={running ? 'animate-spin' : ''} />
            <span>{running ? 'Re-optimizing...' : 'Regenerate Plan'}</span>
          </button>
          <Link
            to="/assessment"
            className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Activity size={14} />
            <span>Movement Screen</span>
          </Link>
        </div>
      </div>

      {/* AI Clinical Movement Screening summary banner */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 shadow-lg relative overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-emerald-900/30">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Activity size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-white">AI Movement Assessment</span>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-500/30 font-medium">
                  {assessments.length > 0 ? 'Verified' : 'Screening Needed'}
                </span>
              </div>
              <p className="text-xs text-emerald-100/60">
                {assessments.length > 0 ? `Last Assessment: ${assessments[0].assessment_date?.substring(0, 10)} • MoveNet Validated` : 'No camera assessment recorded yet'}
              </p>
            </div>
          </div>
          <div className="text-xs text-emerald-400 font-mono">
            Kinematic Engine Confidence: <span className="font-bold text-emerald-300">{assessments.length > 0 ? 'MoveNet Tracked' : 'Pending Screen'}</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
          {/* ROM: Shoulder */}
          <div className="space-y-1">
            <div className="text-xs text-emerald-600 uppercase font-medium">Range of Motion</div>
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-medium text-emerald-200">Shoulder Raise</span>
              <span className="text-2xl font-bold text-white font-mono">
                {shoulderAssess ? `${Math.round(((shoulderAssess.left_measurement || 0) + (shoulderAssess.right_measurement || 0)) / 2)}°` : 'Not Assessed'}
              </span>
            </div>
            <p className="text-xs text-emerald-400/80 flex items-center gap-1.5">
              {shoulderAssess ? (
                <>
                  <CheckCircle size={12} className="text-emerald-400" />
                  <span>Flexion measured via MoveNet pose tracking ({shoulderAssess.assessment_date?.substring(0, 10)}).</span>
                </>
              ) : (
                <Link to="/assessment" className="underline text-emerald-400">
                  Launch camera screen to evaluate shoulder ROM →
                </Link>
              )}
            </p>
          </div>

          {/* Positional Equilibrium */}
          <div className="space-y-1">
            <div className="text-xs text-emerald-600 uppercase font-medium">Positional Equilibrium</div>
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-medium text-emerald-200">One-Leg Stand</span>
              <span className="text-2xl font-bold text-white font-mono">
                {balanceAssess ? `${balanceAssess.left_measurement}s / ${balanceAssess.right_measurement}s` : 'Not Assessed'}
              </span>
            </div>
            <p className="text-xs text-emerald-400/80 flex items-center gap-1.5">
              {balanceAssess ? (
                <>
                  <AlertTriangle size={12} className="text-amber-400" />
                  <span>
                    {Math.abs(balanceAssess.left_measurement - balanceAssess.right_measurement)}s bilateral asymmetry recorded.
                  </span>
                </>
              ) : (
                <Link to="/assessment" className="underline text-emerald-400">
                  Launch camera screen to measure single-leg equilibrium →
                </Link>
              )}
            </p>
          </div>

          {/* Prescription Focus */}
          <div className="space-y-1">
            <div className="text-xs text-emerald-600 uppercase font-medium">Prescription Focus</div>
            <div className="text-sm font-semibold text-white">Assessment Summary</div>
            <p className="text-xs text-emerald-300/80">
              {hasSafetyFlag
                ? 'Gentle joint and posture protocol active based on your health screening.'
                : balanceAssess && Math.abs(balanceAssess.left_measurement - balanceAssess.right_measurement) > 5
                ? 'Your balance test showed a difference between your left and right sides. Your plan includes activities to help improve balance.'
                : 'Focus on building consistent daily movement and balanced muscle control.'}
            </p>
          </div>
        </div>
      </div>

      {/* Six Clinical Pillars Overview Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-white">Your Weekly Plan</h2>
            <p className="text-xs text-emerald-100/60">6 specialist areas combined to improve movement and muscle control</p>
          </div>
          <span className="text-xs text-emerald-400 font-mono bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
            Current Phase: Phase 1 (Activation &amp; Symmetry)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* 1. Physiotherapy */}
          <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 hover:border-emerald-500/40 transition-colors flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                    <Stethoscope size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Physiotherapy</h3>
                    <p className="text-[11px] text-emerald-600">Targeted Rehabilitation</p>
                  </div>
                </div>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  {specialistMap.PHYSIOTHERAPY?.safety_approved ? 'Safety Cleared' : 'Active'}
                </span>
              </div>
              <p className="text-xs text-emerald-100/70 leading-relaxed">
                {specialistMap.PHYSIOTHERAPY?.summary || 'Active rehabilitation for shoulder stabilization and calf strength. Focuses on kinetic chain alignment.'}
              </p>
              <div className="pt-2 border-t border-emerald-900/30 text-[11px] text-emerald-400/80 flex items-center justify-between font-mono">
                <span>Prescribed: {activities.filter(a => a.specialist_name === 'PHYSIOTHERAPY').length} Exercises</span>
                <span>Exercise Order</span>
              </div>
            </div>
            <Link
              to="/specialists/physiotherapy"
              className="mt-4 w-full bg-emerald-500/15 hover:bg-emerald-500 text-emerald-300 hover:text-white py-2 rounded-lg text-xs font-semibold text-center transition-colors block"
            >
              View Physiotherapy Plan →
            </Link>
          </div>

          {/* 2. Nutrition */}
          <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 hover:border-emerald-500/40 transition-colors flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                    <Apple size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Nutrition</h3>
                    <p className="text-[11px] text-emerald-600">Nutrition &amp; Healthy Eating</p>
                  </div>
                </div>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  {specialistMap.NUTRITION?.metrics?.daily_water_target_liters ? `${specialistMap.NUTRITION.metrics.daily_water_target_liters}L Target` : 'Active'}
                </span>
              </div>
              <p className="text-xs text-emerald-100/70 leading-relaxed">
                {specialistMap.NUTRITION?.summary || 'Anti-inflammatory protein synthesis and hydration support. Optimized micronutrient ratios for connective tissue remodeling.'}
              </p>
              <div className="pt-2 border-t border-emerald-900/30 text-[11px] text-emerald-400/80 flex items-center justify-between font-mono">
                <span>Hydration Protocol</span>
                <span>Anti-Inflammatory</span>
              </div>
            </div>
            <Link
              to="/specialists/nutrition"
              className="mt-4 w-full bg-[#111a11] hover:bg-emerald-500/20 text-emerald-300 py-2 rounded-lg text-xs font-semibold text-center transition-colors block"
            >
              View Nutrition Plan →
            </Link>
          </div>

          {/* 3. Behaviour */}
          <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 hover:border-emerald-500/40 transition-colors flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                    <Brain size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Behaviour</h3>
                    <p className="text-[11px] text-emerald-600">Ergonomic Habituation</p>
                  </div>
                </div>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Desk Prompts
                </span>
              </div>
              <p className="text-xs text-emerald-100/70 leading-relaxed">
                {specialistMap.BEHAVIOUR?.summary || 'Micro-habit cues, 45-min desk break triggers, posture resets, and thoracic extension reminders during sedentary intervals.'}
              </p>
              <div className="pt-2 border-t border-emerald-900/30 text-[11px] text-emerald-400/80 flex items-center justify-between font-mono">
                <span>Hourly Movement Prompts</span>
                <span>Active Triggers</span>
              </div>
            </div>
            <Link
              to="/specialists/behaviour"
              className="mt-4 w-full bg-[#111a11] hover:bg-emerald-500/20 text-emerald-300 py-2 rounded-lg text-xs font-semibold text-center transition-colors block"
            >
              View Behaviour Plan →
            </Link>
          </div>

          {/* 4. Wellness & Recovery */}
          <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 hover:border-emerald-500/40 transition-colors flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                    <Moon size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Wellness &amp; Recovery</h3>
                    <p className="text-[11px] text-emerald-600">Rest &amp; Recovery</p>
                  </div>
                </div>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Restorative Wind-Down
                </span>
              </div>
              <p className="text-xs text-emerald-100/70 leading-relaxed">
                {specialistMap.RECOVERY?.summary || 'Circadian sleep tracking and evening mobility wind-down. Parasympathetic activation to accelerate tissue regeneration.'}
              </p>
              <div className="pt-2 border-t border-emerald-900/30 text-[11px] text-emerald-400/80 flex items-center justify-between font-mono">
                <span>Circadian Routine</span>
                <span>Tissue Restoration</span>
              </div>
            </div>
            <Link
              to="/specialists/recovery"
              className="mt-4 w-full bg-[#111a11] hover:bg-emerald-500/20 text-emerald-300 py-2 rounded-lg text-xs font-semibold text-center transition-colors block"
            >
              View Wellness Plan →
            </Link>
          </div>

          {/* 5. Exercise & Activity */}
          <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 hover:border-emerald-500/40 transition-colors flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                    <Dumbbell size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Exercise &amp; Activity</h3>
                    <p className="text-[11px] text-emerald-600">Cardiovascular Volume</p>
                  </div>
                </div>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  {specialistMap.ACTIVITY?.metrics?.recommended_daily_steps ? `${specialistMap.ACTIVITY.metrics.recommended_daily_steps.toLocaleString()} Steps` : 'Active'}
                </span>
              </div>
              <p className="text-xs text-emerald-100/70 leading-relaxed">
                {specialistMap.ACTIVITY?.summary || 'Daily steps tracking, low-impact walking intervals, and active posture walks calibrated to avoid ankle tendon overstrain.'}
              </p>
              <div className="pt-2 border-t border-emerald-900/30 text-[11px] text-emerald-400/80 flex items-center justify-between font-mono">
                <span>Joint Lubrication</span>
                <span>Active Posture Walks</span>
              </div>
            </div>
            <Link
              to="/specialists/activity"
              className="mt-4 w-full bg-[#111a11] hover:bg-emerald-500/20 text-emerald-300 py-2 rounded-lg text-xs font-semibold text-center transition-colors block"
            >
              View Activity Plan →
            </Link>
          </div>

          {/* 6. Progress */}
          <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 hover:border-emerald-500/40 transition-colors flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                    <TrendingUp size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Progress &amp; Biometrics</h3>
                    <p className="text-[11px] text-emerald-600">Your Progress</p>
                  </div>
                </div>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Score: {plan?.overall_score != null ? plan.overall_score : 'Calibrating'}
                </span>
              </div>
              <p className="text-xs text-emerald-100/70 leading-relaxed">
                {specialistMap.PROGRESS?.summary || 'Comparative kinematic curves, asymmetry recovery index, and longitudinal joint mobility scores.'}
              </p>
              <div className="pt-2 border-t border-emerald-900/30 text-[11px] text-emerald-400/80 flex items-center justify-between font-mono">
                <span>MoveWell Biometric Synthesis</span>
                <span>Reassessment Tracked</span>
              </div>
            </div>
            <Link
              to="/progress"
              className="mt-4 w-full bg-[#111a11] hover:bg-emerald-500/20 text-emerald-300 py-2 rounded-lg text-xs font-semibold text-center transition-colors block"
            >
              View Progress Dashboard →
            </Link>
          </div>
        </div>
      </div>

      {/* Today's Prescribed Activities Checklist */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-emerald-900/30">
          <div>
            <h3 className="text-base font-bold text-white">Today's Prescribed Protocol Sequence</h3>
            <p className="text-xs text-emerald-100/60">Executed across Morning, Mid-day, and Evening time-blocks</p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-emerald-400">
            <span>{completedActivities.length} of {activities.length} completed</span>
            <span className="text-emerald-700">|</span>
            <span className="font-bold">{adherencePct}% Adherence</span>
          </div>
        </div>

        <div className="space-y-3">
          {activities.length === 0 ? (
            <p className="text-sm text-emerald-400/60 py-4 text-center">No plan activities generated. Click "Regenerate Plan" above.</p>
          ) : (
            activities.map((act) => {
              const isCompleted = act.completion_status === 'COMPLETED';
              return (
                <div
                  key={act.id}
                  className={`p-4 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                    isCompleted
                      ? 'bg-[#0a120a] border-emerald-900/20 opacity-70'
                      : 'bg-[#111a11] border-emerald-900/40 hover:border-emerald-500/30'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => !isCompleted && handleCompleteActivity(act.id)}
                      disabled={isCompleted}
                      className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center border transition-colors ${
                        isCompleted
                          ? 'bg-emerald-500 border-emerald-400 text-black'
                          : 'border-emerald-700 hover:border-emerald-400 bg-transparent'
                      }`}
                    >
                      {isCompleted && <CheckCircle size={14} className="stroke-[3]" />}
                    </button>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-semibold ${isCompleted ? 'line-through text-emerald-600' : 'text-white'}`}>
                          {act.activity_title}
                        </span>
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                          {act.time_block}
                        </span>
                        <span className="text-[10px] text-emerald-600 font-mono">
                          {act.specialist_name}
                        </span>
                      </div>
                      <p className="text-xs text-emerald-100/60 mt-0.5">{act.activity_description}</p>
                      {act.instructions && (
                        <p className="text-[11px] text-emerald-400/80 mt-1 font-mono">
                          Protocol: {act.instructions}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 sm:self-center">
                    {act.exercise_id && (
                      <Link
                        to={`/exercises/${act.exercise_id}`}
                        className="text-xs bg-[#0f1a0f] border border-emerald-900/60 hover:bg-emerald-500/10 text-emerald-300 px-3 py-1.5 rounded-lg font-medium transition-colors"
                      >
                        Demo &amp; Form
                      </Link>
                    )}
                    {!isCompleted ? (
                      <button
                        onClick={() => handleCompleteActivity(act.id)}
                        className="text-xs bg-emerald-500 hover:bg-emerald-600 text-white px-3 py-1.5 rounded-lg font-semibold transition-colors shadow"
                      >
                        Mark Done
                      </button>
                    ) : (
                      <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
                        <CheckCircle size={12} />
                        <span>Done</span>
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Bottom Row: Weekly Completion Summary & Safety Gate */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weekly Completion Summary */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 shadow-lg flex items-center justify-between gap-6">
          <div className="space-y-2">
            <span className="text-xs text-emerald-500 font-mono uppercase font-semibold">Weekly Completion Summary</span>
            <h3 className="text-xl font-bold text-white">Protocol Adherence</h3>
            <p className="text-xs text-emerald-100/70">
              You've completed <strong className="text-white font-mono">{completedActivities.length} of {activities.length}</strong> prescribed items for today. Consistently achieving over 70% threshold accelerates neuromuscular joint stabilization.
            </p>
            <div className="pt-2">
              <Link
                to="/progress"
                className="text-xs text-emerald-400 hover:text-emerald-300 underline font-mono"
              >
                View Detailed Historical Log →
              </Link>
            </div>
          </div>
          <div className="flex-shrink-0">
            <ScoreRing score={adherencePct} size={90} label="Adherence" />
          </div>
        </div>

        {/* Safety Protocol Notice */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 shadow-lg space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-emerald-400" />
              <h3 className="text-sm font-bold text-white">Safety Protocol Notice</h3>
            </div>
            <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded font-mono">
              Active Protection
            </span>
          </div>
          <p className="text-xs text-emerald-100/70 leading-relaxed">
            If sharp pain exceeding 3/10 occurs during any prescribed movement (such as single-leg balance or shoulder raises), immediately suspend repetition and mark symptom in your check-in.
          </p>
          <div className="pt-2 border-t border-emerald-900/30 flex items-center justify-between text-[11px] font-mono text-emerald-600">
            <span>Safety Gate Engine v2.0</span>
            <span className="text-emerald-400">Continuous Monitoring</span>
          </div>
        </div>
      </div>
    </div>
  );
}
