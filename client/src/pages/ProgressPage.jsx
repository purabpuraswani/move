import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp, Activity, CheckCircle, Clock, Calendar, Download,
  ArrowRight, ShieldCheck, Stethoscope, Apple, Brain, Moon, Sparkles, ChevronRight, AlertCircle
} from 'lucide-react';
import { progressService, assessmentService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function ProgressPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProgress = async () => {
      try {
        setLoading(true);
        const res = await progressService.get();
        setData(res.data);
      } catch (err) {
        console.error('Error fetching progress:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchProgress();
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Synthesizing Longitudinal Biometrics from SQLite..." />
      </div>
    );
  }

  const assessments = data?.assessments || [];
  const shoulderAssessments = assessments.filter(a => a.assessment_type === 'SHOULDER_RAISE');
  const balanceAssessments = assessments.filter(a => a.assessment_type === 'ONE_LEG_STAND');
  const specProgress = data?.specialist_progress || {};

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Breadcrumb & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 font-mono mb-1">
            <span>My Plan &gt; Progress &gt; Your Health &amp; Activity Progress</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Your Progress</h1>
          <p className="text-sm text-emerald-100/70 mt-1 max-w-3xl">
            See how your movement tests, completed exercises, and daily habits improve over time.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/assessment"
            className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg"
          >
            <Calendar size={14} />
            <span>Schedule Assessment</span>
          </Link>
        </div>
      </div>

      {/* 4 Biometric Trajectory Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Overall Recovery */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Overall Wellness Recovery</span>
          <div className="flex items-baseline gap-2">
            {data?.improvement_index_pct !== null && data?.improvement_index_pct !== undefined ? (
              <>
                <span className="text-3xl font-bold text-emerald-400 font-mono">+{data.improvement_index_pct}%</span>
                <span className="text-xs text-emerald-300 font-medium">Improvement Index</span>
              </>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NO HISTORY</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">
            {assessments.length > 0 ? `${assessments.length} kinematics screens on record` : 'Awaiting baseline assessment screen'}
          </p>
        </div>

        {/* Card 2: Symmetry Delta */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Assessment Symmetry Delta</span>
          <div className="flex items-baseline gap-2">
            {data?.symmetry_delta_narrowed_pct !== null && data?.symmetry_delta_narrowed_pct !== undefined ? (
              <span className="text-3xl font-bold text-white font-mono">Narrowed {data.symmetry_delta_narrowed_pct}%</span>
            ) : balanceAssessments.length === 1 ? (
              <span className="text-xl font-bold text-white font-mono">Baseline Logged</span>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT ASSESSED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-400 font-mono">
            {data?.balance_gap_reduction ? `Balance gap: ${data.balance_gap_reduction}` : (balanceAssessments.length > 0 ? `Latest gap: ${Math.abs((balanceAssessments[balanceAssessments.length - 1].left_measurement || 0) - (balanceAssessments[balanceAssessments.length - 1].right_measurement || 0))}s` : 'No balance screen completed')}
          </p>
          <p className="text-[10px] text-emerald-100/60">Stabilizing bilateral kinetic loading</p>
        </div>

        {/* Card 3: Adherence */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Prescribed Exercise Adherence</span>
          <div className="flex items-baseline gap-2">
            {data?.prescribed_adherence_pct !== null && data?.prescribed_adherence_pct !== undefined ? (
              <>
                <span className="text-3xl font-bold text-white font-mono">{data.prescribed_adherence_pct}%</span>
                <span className="text-xs text-emerald-400 font-medium">Compliance rate</span>
              </>
            ) : (
              <span className="text-xl font-bold text-emerald-600 font-mono">NOT LOGGED</span>
            )}
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">
            {data?.total_plan_activities ? `${data.completed_plan_activities || 0} of ${data.total_plan_activities} plan items completed` : 'No active prescribed activities'}
          </p>
        </div>

        {/* Card 4: Screening status */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-1">
          <span className="text-xs text-emerald-600 uppercase font-semibold">Kinematic Screening Status</span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-400 font-mono">
              {assessments.length >= 2 ? 'Reassessment Active' : (assessments.length === 1 ? 'Baseline Set' : 'Screen Required')}
            </span>
          </div>
          <p className="text-[11px] text-emerald-100/60 font-mono">
            {assessments.length > 0 ? `Last: ${assessments[assessments.length - 1].assessment_date?.substring(0, 10)}` : 'MoveNet camera ready'}
          </p>
        </div>
      </div>

      {/* Clinical Movement Screen History & Comparisons */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-6">
        <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
          <div>
            <h2 className="text-base font-bold text-white">Clinical Movement Screen History &amp; Comparisons</h2>
            <p className="text-xs text-emerald-100/60">Kinematic angles and stability measurements validated from SQLite records</p>
          </div>
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
            • MoveNet Kinematic Pose Engine
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Shoulder Raise History */}
          <div className="space-y-4 bg-[#111a11] p-5 rounded-xl border border-emerald-900/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                  <Activity size={16} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Shoulder Raise History</h3>
                  <p className="text-[10px] text-emerald-600 font-mono">Sagittal &amp; Frontal Plane Elevation</p>
                </div>
              </div>
              {data?.shoulder_rom_gain !== null && data?.shoulder_rom_gain !== undefined ? (
                <span className="text-xs font-mono text-emerald-400 font-bold bg-emerald-500/15 px-2 py-0.5 rounded">
                  {data.shoulder_rom_gain >= 0 ? `+${data.shoulder_rom_gain}° ROM Gain` : `${data.shoulder_rom_gain}° ROM Change`}
                </span>
              ) : null}
            </div>

            {shoulderAssessments.length === 0 ? (
              <div className="p-6 text-center border border-dashed border-emerald-900/50 rounded-lg space-y-2">
                <p className="text-xs text-emerald-100/60">No shoulder raise assessments recorded yet.</p>
                <Link to="/assessment" className="text-xs text-emerald-400 font-semibold underline block">
                  Record Baseline Shoulder Screen →
                </Link>
              </div>
            ) : (
              <div className="space-y-3 pt-2">
                {shoulderAssessments.map((item, idx) => {
                  const isLatest = idx === shoulderAssessments.length - 1;
                  const avgAngle = Math.round(((item.left_measurement || 0) + (item.right_measurement || 0)) / 2);
                  return (
                    <div
                      key={item.id}
                      className={`flex items-start justify-between border-l-2 ${
                        isLatest ? 'border-emerald-400 bg-emerald-500/5 p-2 rounded-r' : 'border-emerald-900 pl-3'
                      }`}
                    >
                      <div>
                        <span className={`text-[11px] font-mono ${isLatest ? 'text-emerald-400 font-bold' : 'text-emerald-600'}`}>
                          {idx === 0 ? 'Baseline' : (isLatest ? '• Current' : 'Mid-Cycle')} ({item.assessment_date?.substring(0, 10)})
                        </span>
                        <p className="text-xs text-emerald-100/80 mt-0.5">
                          {avgAngle >= 155 ? 'Flexion within optimal functional band' : 'Compensatory scapular rhythm flagged'}
                        </p>
                      </div>
                      <span className={`font-mono font-bold ${isLatest ? 'text-xl text-emerald-400' : 'text-base text-emerald-300'}`}>
                        {avgAngle}°
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="pt-2 border-t border-emerald-900/30 flex items-center justify-between text-[11px] font-mono text-emerald-600">
              <span>Normal Functional Target: 180°</span>
              <span className="text-emerald-400 font-bold">
                {data?.shoulder_current ? `${Math.round((data.shoulder_current / 180) * 100)}% of Goal` : 'Target: 180°'}
              </span>
            </div>
          </div>

          {/* One-Leg Stand Balance History */}
          <div className="space-y-4 bg-[#111a11] p-5 rounded-xl border border-emerald-900/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                  <Activity size={16} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">One-Leg Stand Balance History</h3>
                  <p className="text-[10px] text-emerald-600 font-mono">Vestibular &amp; Unilateral Proprioception</p>
                </div>
              </div>
              {data?.symmetry_delta_narrowed_pct !== null && data?.symmetry_delta_narrowed_pct !== undefined ? (
                <span className="text-xs font-mono text-emerald-400 font-bold bg-emerald-500/15 px-2 py-0.5 rounded">
                  -{data.symmetry_delta_narrowed_pct}% Asymmetry
                </span>
              ) : null}
            </div>

            {balanceAssessments.length === 0 ? (
              <div className="p-6 text-center border border-dashed border-emerald-900/50 rounded-lg space-y-2">
                <p className="text-xs text-emerald-100/60">No single-leg balance assessments recorded yet.</p>
                <Link to="/assessment" className="text-xs text-emerald-400 font-semibold underline block">
                  Record Balance Screen →
                </Link>
              </div>
            ) : (
              <div className="space-y-3 pt-2">
                {balanceAssessments.map((item, idx) => {
                  const isLatest = idx === balanceAssessments.length - 1;
                  const gap = Math.abs((item.left_measurement || 0) - (item.right_measurement || 0));
                  return (
                    <div
                      key={item.id}
                      className={`flex items-center justify-between border-l-2 ${
                        isLatest ? 'border-emerald-400 bg-emerald-500/5 p-2 rounded-r' : 'border-emerald-900 pl-3'
                      }`}
                    >
                      <span className={`text-[11px] font-mono ${isLatest ? 'text-emerald-400 font-bold' : 'text-emerald-600'}`}>
                        {idx === 0 ? 'Baseline' : (isLatest ? '• Current' : 'Mid-Cycle')} ({item.assessment_date?.substring(0, 10)})
                      </span>
                      <div className="flex items-center gap-3 text-xs font-mono">
                        <span>Left: <strong className={isLatest ? 'text-emerald-400' : 'text-white'}>{item.left_measurement}s</strong></span>
                        <span>Right: <strong className={isLatest ? 'text-emerald-400' : 'text-white'}>{item.right_measurement}s</strong></span>
                        <span className={`font-bold ${gap > 5 ? 'text-amber-400' : 'text-emerald-300'}`}>
                          {gap}s gap
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="pt-2 border-t border-emerald-900/30 flex items-center justify-between text-[11px] font-mono text-emerald-600">
              <span>Target Delta Threshold: &lt; 5s gap</span>
              <span className="text-emerald-400 font-bold">
                {balanceAssessments.length > 0 && Math.abs((balanceAssessments[balanceAssessments.length - 1].left_measurement || 0) - (balanceAssessments[balanceAssessments.length - 1].right_measurement || 0)) <= 5
                  ? 'Within Balanced Threshold'
                  : 'Stabilization Required'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Multi-Disciplinary Pillar Progress Overview */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
        <div>
          <h2 className="text-base font-bold text-white">Multi-Disciplinary Pillar Progress Overview</h2>
          <p className="text-xs text-emerald-100/60">Adherence and activity tracking derived from your real database logs</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Physiotherapy */}
          <div className="bg-[#111a11] border border-emerald-900/40 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white">Physiotherapy</span>
              <span className="text-xs font-mono text-emerald-400">
                {specProgress.physiotherapy?.compliance_pct !== null ? `${specProgress.physiotherapy.compliance_pct}%` : 'Pending'}
              </span>
            </div>
            <p className="text-[11px] text-emerald-100/70">{specProgress.physiotherapy?.status}</p>
            <span className="text-[10px] text-emerald-500 font-mono block">
              {specProgress.physiotherapy?.completed_sets || 0} completed sets
            </span>
          </div>

          {/* Nutrition */}
          <div className="bg-[#111a11] border border-emerald-900/40 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white">Nutrition</span>
              <span className="text-xs font-mono text-emerald-400">
                {specProgress.nutrition?.logging_consistency_pct !== null ? `${specProgress.nutrition.logging_consistency_pct}%` : 'Not Logged'}
              </span>
            </div>
            <p className="text-[11px] text-emerald-100/70">{specProgress.nutrition?.status}</p>
            <span className="text-[10px] text-emerald-500 font-mono block">
              {specProgress.nutrition?.total_logged || 0} total meal logs on record
            </span>
          </div>

          {/* Behaviour */}
          <div className="bg-[#111a11] border border-emerald-900/40 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white">Behaviour</span>
              <span className="text-xs font-mono text-emerald-400">
                {specProgress.behaviour?.desk_break_compliance_pct !== null ? `${specProgress.behaviour.desk_break_compliance_pct}%` : '0%'}
              </span>
            </div>
            <p className="text-[11px] text-emerald-100/70">{specProgress.behaviour?.status}</p>
            <span className="text-[10px] text-emerald-500 font-mono block">
              {specProgress.behaviour?.streak_days || 0}-day habit consistency
            </span>
          </div>

          {/* Recovery */}
          <div className="bg-[#111a11] border border-emerald-900/40 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white">Wellness &amp; Recovery</span>
              <span className="text-xs font-mono text-emerald-400">
                {specProgress.recovery?.avg_sleep_hours ? `${specProgress.recovery.avg_sleep_hours} hrs` : 'Not Logged'}
              </span>
            </div>
            <p className="text-[11px] text-emerald-100/70">{specProgress.recovery?.status}</p>
            <span className="text-[10px] text-emerald-500 font-mono block">
              {specProgress.recovery?.stress_rating ? `Stress score ${specProgress.recovery.stress_rating}/100` : 'Pending sleep logs'}
            </span>
          </div>
        </div>
      </div>

      {/* Progress Timeline & Milestones */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
          <div>
            <h2 className="text-base font-bold text-white">Progress Timeline &amp; Milestones</h2>
            <p className="text-xs text-emerald-100/60">Phased progression criteria based on biomechanical benchmark thresholds</p>
          </div>
          <span className="text-xs font-mono text-emerald-600">Current Cycle: 12-Week Roadmap</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Phase 1 */}
          <div className="bg-[#111a11] border-2 border-emerald-500/50 rounded-xl p-5 space-y-3 relative">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-emerald-400 font-mono">PHASE 1 (CURRENT)</span>
              <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded font-mono font-bold">
                {data?.prescribed_adherence_pct !== null && data?.prescribed_adherence_pct !== undefined ? `${data.prescribed_adherence_pct}% Completed` : 'In Progress'}
              </span>
            </div>
            <h3 className="text-sm font-bold text-white">Activation &amp; Symmetry</h3>
            <p className="text-xs text-emerald-100/70">
              Focus on correcting unilateral compensations, stabilizing core firing sequences, and restoring basic shoulder ROM.
            </p>
            <ul className="text-xs space-y-1.5 text-emerald-300 font-mono pt-2">
              <li className="flex items-center gap-1.5">✓ Unilateral hip stabilizer activation</li>
              <li className="flex items-center gap-1.5">✓ Scapular upward rotation rhythm</li>
              <li className="flex items-center gap-1.5 text-emerald-400">⦿ Biomechanical Reassessment</li>
            </ul>
          </div>

          {/* Phase 2 */}
          <div className="bg-[#111a11] border border-emerald-900/40 rounded-xl p-5 space-y-3 opacity-80">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-emerald-700 font-mono">PHASE 2</span>
              <span className="text-xs text-emerald-600 font-mono">Kinematic Progression</span>
            </div>
            <h3 className="text-sm font-bold text-white">Kinematic Load Progression</h3>
            <p className="text-xs text-emerald-100/70">
              Integrating multi-planar resistance bands and compound dynamic balances to prepare kinetic chains for dynamic loading.
            </p>
            <ul className="text-xs space-y-1.5 text-emerald-700 font-mono pt-2">
              <li>○ Resemble posterior chain loading</li>
              <li>○ Overhead stability under light tension</li>
              <li>○ Mid-thoracic mobility drills</li>
            </ul>
          </div>

          {/* Phase 3 */}
          <div className="bg-[#111a11] border border-emerald-900/40 rounded-xl p-5 space-y-3 opacity-60">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-emerald-800 font-mono">PHASE 3</span>
              <span className="text-xs text-emerald-700 font-mono">Peak Recovery</span>
            </div>
            <h3 className="text-sm font-bold text-white">Functional Agility &amp; Return to Peak</h3>
            <p className="text-xs text-emerald-100/70">
              Full dynamic movement patterns, athletic deceleration, and sustained endurance across all athletic protocols.
            </p>
            <ul className="text-xs space-y-1.5 text-emerald-800 font-mono pt-2">
              <li>○ Full sport-specific biomechanics</li>
              <li>○ Maximal asymmetry tolerance &lt; 5%</li>
              <li>○ Self-regulated maintenance regimen</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Clinical Decision Support Callout */}
      <div className="bg-[#0f1a0f] border border-emerald-500/30 rounded-xl p-5 flex flex-wrap items-center justify-between gap-4 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 flex-shrink-0">
            <ShieldCheck size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-white">Clinical Decision Support</span>
              <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded font-mono">Six Specialist Synthesis</span>
            </div>
            <p className="text-xs text-emerald-100/80 mt-0.5">
              {assessments.length > 0
                ? 'Clinical findings active. Reassessment unlocks next-stage progression criteria.'
                : 'Complete your first movement screen to initialize multi-specialist diagnostic synthesis.'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/plan"
            className="text-xs bg-[#111a11] border border-emerald-900/60 hover:bg-emerald-500/10 text-emerald-300 px-4 py-2 rounded-lg font-medium transition-colors"
          >
            View Active Plan
          </Link>
          <Link
            to="/assessment"
            className="text-xs bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg font-semibold transition-colors flex items-center gap-1.5"
          >
            <span>Start Kinematic Assessment</span>
            <ArrowRight size={13} />
          </Link>
        </div>
      </div>
    </div>
  );
}
