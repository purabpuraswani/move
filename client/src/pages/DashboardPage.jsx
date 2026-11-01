import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp, Activity, Heart, Moon, Apple, Brain, Dumbbell, Stethoscope,
  ChevronRight, RefreshCw, AlertCircle, PlayCircle, CheckCircle, Clock
} from 'lucide-react';
import { useAuth } from '../App';
import { planService, progressService, assessmentService, workflowService } from '../services/api';
import ScoreRing from '../components/common/ScoreRing';
import LoadingSpinner from '../components/common/LoadingSpinner';
import TrendLine from '../components/charts/TrendLine';

const SPECIALIST_META = [
  { key: 'physiotherapy', label: 'Physiotherapy', icon: Stethoscope, path: '/specialists/physiotherapy', color: 'text-blue-400' },
  { key: 'nutrition', label: 'Nutrition', icon: Apple, path: '/specialists/nutrition', color: 'text-orange-400' },
  { key: 'behaviour', label: 'Behaviour', icon: Brain, path: '/specialists/behaviour', color: 'text-purple-400' },
  { key: 'recovery', label: 'Wellness & Recovery', icon: Moon, path: '/specialists/recovery', color: 'text-indigo-400' },
  { key: 'activity', label: 'Exercise & Activity', icon: Dumbbell, path: '/specialists/activity', color: 'text-emerald-400' },
  { key: 'progress', label: 'Progress & Biometrics', icon: TrendingUp, path: '/progress', color: 'text-teal-400' },
];

function SkeletonCard({ h = 'h-24' }) {
  return <div className={`bg-[#0f1a0f] border border-emerald-900/30 rounded-xl ${h} animate-pulse`} />;
}

function formatDisplayDate(dateStr) {
  if (!dateStr) return 'Not recorded';
  try {
    const cleanStr = dateStr.includes('T') ? dateStr : dateStr.replace(' ', 'T');
    const d = new Date(cleanStr);
    if (isNaN(d.getTime())) return dateStr.substring(0, 10);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr.substring(0, 10);
  }
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [plan, setPlan] = useState(null);
  const [progress, setProgress] = useState(null);
  const [assessments, setAssessments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningWorkflow, setRunningWorkflow] = useState(false);
  const [workflowMsg, setWorkflowMsg] = useState('');

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const [planRes, progressRes, assessRes] = await Promise.allSettled([
          planService.current(),
          progressService.get(),
          assessmentService.getAll(),
        ]);
        if (planRes.status === 'fulfilled') setPlan(planRes.value.data);
        if (progressRes.status === 'fulfilled') setProgress(progressRes.value.data);
        if (assessRes.status === 'fulfilled') setAssessments(assessRes.value.data || []);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  const handleRunWorkflow = async () => {
    setRunningWorkflow(true);
    setWorkflowMsg('');
    try {
      await workflowService.run();
      setWorkflowMsg('Workflow completed! Refreshing...');
      setTimeout(() => window.location.reload(), 1500);
    } catch (err) {
      setWorkflowMsg(err.response?.data?.error || 'Workflow failed. Please try again.');
    } finally {
      setRunningWorkflow(false);
    }
  };

  const shoulderAssess = assessments.find(a => a.assessment_type === 'SHOULDER_RAISE');
  const balanceAssess = assessments.find(a => a.assessment_type === 'ONE_LEG_STAND');
  const hasFullAssessment = !!(shoulderAssess && balanceAssess);
  const hasPartialAssessment = !!(shoulderAssess || balanceAssess);
  const latestAssessmentDate = assessments[0]?.assessment_date;

  const moveScore = plan?.movewell_score ?? progress?.movewell_score ?? null;
  const activityScore = plan?.activity_score ?? null;

  // Single source of truth for plan activities
  const todayActivities = plan?.activities || plan?.plan_activities || [];
  const completedCount = todayActivities.filter(a => a.completion_status === 'COMPLETED' || a.completed).length;
  const completionPct = todayActivities.length ? Math.round((completedCount / todayActivities.length) * 100) : 0;

  const scoreHistory = progress?.score_history || [];

  const morning = todayActivities.filter(a => (a.time_block || '').toLowerCase() === 'morning').slice(0, 3);
  const evening = todayActivities.filter(a => (a.time_block || '').toLowerCase() === 'evening').slice(0, 3);
  const anytime = todayActivities.filter(a => (a.time_block || '').toLowerCase() === 'anytime' || !a.time_block).slice(0, 2);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Good {new Date().getHours() < 12 ? 'Morning' : new Date().getHours() < 17 ? 'Afternoon' : 'Evening'}, {user?.name?.split(' ')[0] ?? 'there'} 👋
          </h1>
          <p className="text-emerald-400/60 text-sm mt-1">Here's your wellness overview for today.</p>
        </div>
        <button
          onClick={handleRunWorkflow}
          disabled={runningWorkflow}
          className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 text-emerald-400 rounded-lg px-4 py-2.5 text-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={runningWorkflow ? 'animate-spin' : ''} />
          {runningWorkflow ? 'Generating...' : 'Generate Plan'}
        </button>
      </div>

      {workflowMsg && (
        <div className={`rounded-lg px-4 py-2.5 text-sm ${workflowMsg.includes('failed') ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'}`}>
          {workflowMsg}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <SkeletonCard h="h-48" />
            <SkeletonCard h="h-48" />
            <SkeletonCard h="h-48" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SkeletonCard h="h-64" />
            <SkeletonCard h="h-64" />
          </div>
        </div>
      ) : (
        <>
          {/* Top score cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* MoveWell Score */}
            <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 flex items-center gap-6">
              <ScoreRing score={moveScore ?? 0} size={110} label="Score" />
              <div className="flex-1">
                <div className="text-xs text-emerald-400/60 uppercase tracking-wide mb-1">MoveWell Score</div>
                <div className="text-white font-semibold text-sm mb-1">
                  {moveScore === null
                    ? 'No score yet'
                    : moveScore >= 80
                    ? 'Excellent'
                    : moveScore >= 60
                    ? 'Good'
                    : moveScore >= 35
                    ? 'Developing'
                    : 'Calibration Phase'}
                </div>
                <div className="text-xs text-emerald-500/70 mb-2">
                  {completedCount === 0
                    ? '0 exercises logged — complete workouts to increase score'
                    : `${completedCount} of ${todayActivities.length} daily activities completed`}
                </div>
                {scoreHistory.length > 1 && (
                  <TrendLine data={scoreHistory.slice(-7).map(s => ({ value: s.score }))} />
                )}
                <Link to="/progress" className="text-xs text-emerald-500 hover:text-emerald-400 flex items-center gap-1 mt-2">
                  View biometrics &amp; trends <ChevronRight size={10} />
                </Link>
              </div>
            </div>

            {/* Today's Progress */}
            <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6">
              <div className="text-xs text-emerald-400/60 uppercase tracking-wide mb-4">Today's Progress</div>
              {todayActivities.length === 0 ? (
                <div className="text-center py-4">
                  <PlayCircle size={28} className="text-emerald-700 mx-auto mb-2" />
                  <p className="text-emerald-400/50 text-xs">No plan generated yet.</p>
                  <button onClick={handleRunWorkflow} className="mt-2 text-xs text-emerald-500 hover:text-emerald-400 underline">Generate now</button>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between mb-3">
                    <ScoreRing score={completionPct} size={80} label="Done" />
                    <div className="text-right">
                      <div className="text-2xl font-bold text-white">{completedCount}/{todayActivities.length}</div>
                      <div className="text-xs text-emerald-400/60">activities</div>
                    </div>
                  </div>
                  <div className="w-full bg-[#0a0f0a] rounded-full h-1.5 mt-2">
                    <div
                      className="bg-emerald-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${completionPct}%` }}
                    />
                  </div>
                  <Link to="/plan" className="text-xs text-emerald-500 hover:text-emerald-400 flex items-center gap-1 mt-3">
                    View full plan <ChevronRight size={10} />
                  </Link>
                </>
              )}
            </div>

            {/* Assessment status */}
            <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6">
              <div className="text-xs text-emerald-400/60 uppercase tracking-wide mb-4">Movement Assessment</div>
              {hasFullAssessment ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle size={14} className="text-emerald-400" />
                    <span className="text-sm font-semibold text-white">Assessment Complete</span>
                  </div>
                  <div className="text-xs text-emerald-400/50">
                    Validated on {formatDisplayDate(latestAssessmentDate)}
                  </div>
                  <div className="space-y-2 mt-3 pt-2 border-t border-emerald-900/30">
                    <div className="flex justify-between text-xs">
                      <span className="text-emerald-400/60">Shoulder Raise</span>
                      <span className="text-white font-mono">{shoulderAssess.left_measurement}° L / {shoulderAssess.right_measurement}° R</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-emerald-400/60">One-Leg Stand</span>
                      <span className="text-white font-mono">{balanceAssess.left_measurement}s L / {balanceAssess.right_measurement}s R</span>
                    </div>
                  </div>
                  <Link to="/assessment" className="text-xs text-emerald-500 hover:text-emerald-400 flex items-center gap-1 mt-2">
                    Retake assessment <ChevronRight size={10} />
                  </Link>
                </div>
              ) : hasPartialAssessment ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Clock size={14} className="text-amber-400" />
                    <span className="text-sm font-semibold text-white">Partial Assessment</span>
                  </div>
                  <div className="text-xs text-amber-400/70">
                    {shoulderAssess ? 'Shoulder Raise completed. Balance test pending.' : 'Balance test completed. Shoulder test pending.'}
                  </div>
                  <div className="space-y-2 mt-2 pt-2 border-t border-emerald-900/30">
                    {shoulderAssess && (
                      <div className="flex justify-between text-xs">
                        <span className="text-emerald-400/60">Shoulder Raise</span>
                        <span className="text-white font-mono">{shoulderAssess.left_measurement}° L / {shoulderAssess.right_measurement}° R</span>
                      </div>
                    )}
                    {balanceAssess && (
                      <div className="flex justify-between text-xs">
                        <span className="text-emerald-400/60">One-Leg Stand</span>
                        <span className="text-white font-mono">{balanceAssess.left_measurement}s L / {balanceAssess.right_measurement}s R</span>
                      </div>
                    )}
                  </div>
                  <Link to="/assessment" className="text-xs text-emerald-400 hover:text-emerald-300 underline block mt-2">
                    Complete remaining assessment test →
                  </Link>
                </div>
              ) : (
                <div className="text-center py-4">
                  <AlertCircle size={28} className="text-yellow-500 mx-auto mb-2" />
                  <p className="text-emerald-400/60 text-xs mb-3">No camera assessment recorded yet.</p>
                  <Link to="/assessment" className="inline-flex items-center gap-1.5 bg-emerald-500 text-white rounded-lg px-4 py-2 text-xs font-medium hover:bg-emerald-600 transition-colors">
                    <PlayCircle size={12} />
                    Start Camera Assessment
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Today's plan preview */}
          {todayActivities.length > 0 && (
            <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-white font-semibold">Today's Activities</h2>
                <Link to="/plan" className="text-xs text-emerald-500 hover:text-emerald-400 flex items-center gap-1">
                  View all <ChevronRight size={10} />
                </Link>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {morning.length > 0 && (
                  <div>
                    <div className="text-xs text-emerald-600 uppercase tracking-wider font-semibold mb-2">☀️ Morning</div>
                    {morning.map((a, i) => {
                      const isDone = a.completion_status === 'COMPLETED' || a.completed;
                      const title = a.activity_title || a.title;
                      return (
                        <div key={i} className="flex items-center gap-2 py-2 border-b border-emerald-900/20 last:border-0">
                          {isDone
                            ? <CheckCircle size={14} className="text-emerald-400 flex-shrink-0" />
                            : <div className="w-3.5 h-3.5 rounded-full border border-emerald-700 flex-shrink-0" />
                          }
                          <span className={`text-xs ${isDone ? 'line-through text-emerald-400/40' : 'text-white'}`}>{title}</span>
                          <span className="ml-auto text-xs text-emerald-600 flex items-center gap-0.5 font-mono">
                            <Clock size={9} />{a.duration_minutes || 10}m
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
                {evening.length > 0 && (
                  <div>
                    <div className="text-xs text-emerald-600 uppercase tracking-wider font-semibold mb-2">🌙 Evening</div>
                    {evening.map((a, i) => {
                      const isDone = a.completion_status === 'COMPLETED' || a.completed;
                      const title = a.activity_title || a.title;
                      return (
                        <div key={i} className="flex items-center gap-2 py-2 border-b border-emerald-900/20 last:border-0">
                          {isDone
                            ? <CheckCircle size={14} className="text-emerald-400 flex-shrink-0" />
                            : <div className="w-3.5 h-3.5 rounded-full border border-emerald-700 flex-shrink-0" />
                          }
                          <span className={`text-xs ${isDone ? 'line-through text-emerald-400/40' : 'text-white'}`}>{title}</span>
                          <span className="ml-auto text-xs text-emerald-600 flex items-center gap-0.5 font-mono">
                            <Clock size={9} />{a.duration_minutes || 10}m
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
                {anytime.length > 0 && (
                  <div>
                    <div className="text-xs text-emerald-600 uppercase tracking-wider font-semibold mb-2">🕐 Anytime</div>
                    {anytime.map((a, i) => {
                      const isDone = a.completion_status === 'COMPLETED' || a.completed;
                      const title = a.activity_title || a.title;
                      return (
                        <div key={i} className="flex items-center gap-2 py-2 border-b border-emerald-900/20 last:border-0">
                          {isDone
                            ? <CheckCircle size={14} className="text-emerald-400 flex-shrink-0" />
                            : <div className="w-3.5 h-3.5 rounded-full border border-emerald-700 flex-shrink-0" />
                          }
                          <span className={`text-xs ${isDone ? 'line-through text-emerald-400/40' : 'text-white'}`}>{title}</span>
                          <span className="ml-auto text-xs text-emerald-600 flex items-center gap-0.5 font-mono">
                            <Clock size={9} />{a.duration_minutes || 10}m
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Specialist cards */}
          <div>
            <h2 className="text-white font-semibold mb-3">Your Specialists</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {SPECIALIST_META.map(({ key, label, icon: Icon, path, color }) => {
                const specData = plan?.specialist_summaries?.[key];
                return (
                  <Link
                    key={key}
                    to={path}
                    className="bg-[#0f1a0f] border border-emerald-900/40 hover:border-emerald-500/40 rounded-xl p-4 flex items-start gap-3 transition-colors group"
                  >
                    <div className="w-8 h-8 bg-[#0a0f0a] rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Icon size={16} className={color} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-white group-hover:text-emerald-300 transition-colors">{label}</div>
                      <div className="text-xs text-emerald-400/50 mt-0.5 line-clamp-2">
                        {specData?.summary || specData?.finding || 'No recommendations yet. Complete your assessment.'}
                      </div>
                    </div>
                    <ChevronRight size={14} className="text-emerald-700 group-hover:text-emerald-400 transition-colors flex-shrink-0 mt-1" />
                  </Link>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
