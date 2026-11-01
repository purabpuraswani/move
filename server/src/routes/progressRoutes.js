import express from 'express';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';
import { loadUserContext, calculateLiveMoveWellScore } from '../orchestrator/workflowOrchestrator.js';
import { runProgressAgent } from '../agents/progressAgent.js';

const router = express.Router();

// GET /api/progress - Comprehensive progress overview
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const userContext = loadUserContext(req.userId);
    const progressOutput = runProgressAgent(userContext);

    // Get latest health plan
    const latestPlan = db.prepare(`
      SELECT * FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
    `).get(req.userId);

    // Get all movement assessments in chronological order
    const assessments = db.prepare(`
      SELECT * FROM movement_assessments WHERE user_id = ? ORDER BY assessment_date ASC
    `).all(req.userId);

    // Completed activities
    const completedActivities = db.prepare(`
      SELECT ac.*, pa.activity_title, pa.specialist_name, pa.time_block
      FROM activity_completions ac
      JOIN plan_activities pa ON ac.plan_activity_id = pa.id
      WHERE ac.user_id = ? ORDER BY ac.completed_at DESC LIMIT 25
    `).all(req.userId);

    // Calculate genuine protocol adherence
    let prescribedAdherence = null;
    let totalPlanActivities = 0;
    let completedPlanActivities = 0;
    if (latestPlan) {
      totalPlanActivities = db.prepare('SELECT COUNT(*) as c FROM plan_activities WHERE plan_id = ?').get(latestPlan.id).c;
      completedPlanActivities = db.prepare(`
        SELECT COUNT(*) as c FROM activity_completions ac
        JOIN plan_activities pa ON ac.plan_activity_id = pa.id
        WHERE pa.plan_id = ? AND ac.user_id = ?
      `).get(latestPlan.id, req.userId).c;

      if (totalPlanActivities > 0) {
        prescribedAdherence = Math.round((completedPlanActivities / totalPlanActivities) * 100);
      }
    }

    // Kinematic screen history
    const shoulderAssessments = assessments.filter(a => a.assessment_type === 'SHOULDER_RAISE');
    const balanceAssessments = assessments.filter(a => a.assessment_type === 'ONE_LEG_STAND');

    let shoulderRomGain = null;
    let shoulderBaseline = null;
    let shoulderCurrent = null;
    if (shoulderAssessments.length > 0) {
      const first = shoulderAssessments[0];
      const last = shoulderAssessments[shoulderAssessments.length - 1];
      shoulderBaseline = Math.round(((first.left_measurement || 0) + (first.right_measurement || 0)) / 2);
      shoulderCurrent = Math.round(((last.left_measurement || 0) + (last.right_measurement || 0)) / 2);
      if (shoulderAssessments.length >= 2) {
        shoulderRomGain = shoulderCurrent - shoulderBaseline;
      }
    }

    let symmetryNarrowedPct = null;
    let balanceGapReduction = null;
    let balanceBaseline = null;
    let balanceCurrent = null;
    if (balanceAssessments.length > 0) {
      const first = balanceAssessments[0];
      const last = balanceAssessments[balanceAssessments.length - 1];
      const firstGap = Math.abs((first.left_measurement || 0) - (first.right_measurement || 0));
      const lastGap = Math.abs((last.left_measurement || 0) - (last.right_measurement || 0));
      balanceBaseline = { left: first.left_measurement, right: first.right_measurement, gap: firstGap };
      balanceCurrent = { left: last.left_measurement, right: last.right_measurement, gap: lastGap };

      if (balanceAssessments.length >= 2 && firstGap > 0) {
        symmetryNarrowedPct = Math.max(0, Math.round(((firstGap - lastGap) / firstGap) * 100));
        balanceGapReduction = `${firstGap}s → ${lastGap}s`;
      }
    }

    // Genuine multidisciplinary pillars progress
    const physioTotal = latestPlan ? db.prepare("SELECT COUNT(*) as c FROM plan_activities WHERE plan_id = ? AND specialist_name = 'PHYSIOTHERAPY'").get(latestPlan.id).c : 0;
    const physioDone = latestPlan ? db.prepare("SELECT COUNT(*) as c FROM activity_completions ac JOIN plan_activities pa ON ac.plan_activity_id = pa.id WHERE pa.plan_id = ? AND pa.specialist_name = 'PHYSIOTHERAPY' AND ac.user_id = ?").get(latestPlan.id, req.userId).c : 0;

    const mealCountToday = db.prepare("SELECT COUNT(*) as c FROM meal_logs WHERE user_id = ? AND date(logged_at) = date('now')").get(req.userId).c;
    const totalMealsLogged = db.prepare("SELECT COUNT(*) as c FROM meal_logs WHERE user_id = ?").get(req.userId).c;

    const habitRecords = db.prepare("SELECT * FROM behaviour_records WHERE user_id = ? ORDER BY record_date DESC").all(req.userId);
    const completedHabits = habitRecords.filter(h => h.status === 'COMPLETED').length;
    const habitStreak = habitRecords.length > 0 ? new Set(habitRecords.map(h => h.record_date)).size : 0;

    const sleepStats = db.prepare("SELECT AVG(sleep_duration) as avg_sleep, AVG(stress_level) as avg_stress, COUNT(*) as c FROM sleep_records WHERE user_id = ?").get(req.userId);

    const specialistStats = {
      physiotherapy: {
        completed_sets: physioDone,
        target_sets: physioTotal,
        compliance_pct: physioTotal > 0 ? Math.round((physioDone / physioTotal) * 100) : (assessments.length > 0 ? 100 : null),
        status: physioTotal > 0 ? `${physioDone} of ${physioTotal} prescribed activities completed` : (assessments.length > 0 ? 'Kinematics assessed' : 'Pending assessment')
      },
      nutrition: {
        meals_logged_today: mealCountToday,
        total_logged: totalMealsLogged,
        logging_consistency_pct: totalMealsLogged > 0 ? Math.min(100, Math.round((mealCountToday / 3) * 100)) : null,
        status: totalMealsLogged > 0 ? `${mealCountToday}/3 meals logged today` : 'No meals logged yet'
      },
      behaviour: {
        streak_days: habitStreak,
        desk_break_compliance_pct: habitRecords.length > 0 ? Math.round((completedHabits / habitRecords.length) * 100) : null,
        status: habitRecords.length > 0 ? `${habitStreak}-day streak maintained` : 'No habit records logged'
      },
      recovery: {
        avg_sleep_hours: sleepStats.c > 0 && sleepStats.avg_sleep ? parseFloat(sleepStats.avg_sleep.toFixed(1)) : null,
        stress_rating: sleepStats.c > 0 && sleepStats.avg_stress ? Math.round(sleepStats.avg_stress * 10) : null,
        status: sleepStats.c > 0 ? `Avg sleep ${sleepStats.avg_sleep.toFixed(1)} hrs` : 'No recovery check-ins logged'
      }
    };

    // Calculate genuine improvement index based on completed activities and assessments
    let improvementIndex = null;
    if (assessments.length >= 2 || completedPlanActivities > 0) {
      let score = 0;
      if (shoulderRomGain && shoulderRomGain > 0) score += Math.min(8, shoulderRomGain);
      if (symmetryNarrowedPct && symmetryNarrowedPct > 0) score += Math.min(8, Math.round(symmetryNarrowedPct / 4));
      if (prescribedAdherence) score += Math.round(prescribedAdherence * 0.08);
      improvementIndex = Math.max(1, score);
    }

    const liveScore = calculateLiveMoveWellScore(req.userId);

    res.json({
      movewell_score: liveScore.overall_score,
      score_breakdown: liveScore.breakdown,
      improvement_index_pct: improvementIndex,
      symmetry_delta_narrowed_pct: symmetryNarrowedPct,
      balance_gap_reduction: balanceGapReduction,
      balance_baseline: balanceBaseline,
      balance_current: balanceCurrent,
      shoulder_rom_gain: shoulderRomGain,
      shoulder_baseline: shoulderBaseline,
      shoulder_current: shoulderCurrent,
      prescribed_adherence_pct: prescribedAdherence,
      total_plan_activities: totalPlanActivities,
      completed_plan_activities: completedPlanActivities,
      assessments,
      completed_activities: completedActivities,
      specialist_progress: specialistStats,
      progress_agent_output: progressOutput
    });
  } catch (err) {
    console.error('Progress fetch error:', err);
    res.status(500).json({ error: 'Failed to fetch progress overview' });
  }
});

// GET /api/progress/trends
router.get('/trends', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const activityTrend = db.prepare(`
      SELECT record_date, daily_steps, sitting_hours, movement_breaks
      FROM activity_records WHERE user_id = ? ORDER BY record_date ASC LIMIT 14
    `).all(req.userId);

    const sleepTrend = db.prepare(`
      SELECT record_date, sleep_duration, stress_level, sleep_quality
      FROM sleep_records WHERE user_id = ? ORDER BY record_date ASC LIMIT 14
    `).all(req.userId);

    const assessments = db.prepare(`
      SELECT assessment_type, left_measurement, right_measurement, assessment_date
      FROM movement_assessments WHERE user_id = ? ORDER BY assessment_date ASC
    `).all(req.userId);

    res.json({
      activity_trend: activityTrend,
      sleep_trend: sleepTrend,
      assessments
    });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch progress trends' });
  }
});

export default router;

