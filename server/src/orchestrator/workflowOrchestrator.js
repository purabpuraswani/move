import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { runPhysiotherapyAgent } from '../agents/physiotherapyAgent.js';
import { runNutritionAgent } from '../agents/nutritionAgent.js';
import { runBehaviourAgent } from '../agents/behaviourAgent.js';
import { runRecoveryAgent } from '../agents/recoveryAgent.js';
import { runActivityAgent } from '../agents/activityAgent.js';
import { runProgressAgent } from '../agents/progressAgent.js';

/**
 * Loads all user context data needed by specialist agents (single source of truth).
 */
export function loadUserContext(userId) {
  const db = getDb();

  const user = db.prepare('SELECT id, name, email, created_at FROM users WHERE id = ?').get(userId);
  const profile = db.prepare('SELECT * FROM user_profiles WHERE user_id = ?').get(userId);
  const health_screening = db.prepare('SELECT * FROM health_screenings WHERE user_id = ? ORDER BY completed_at DESC LIMIT 1').get(userId);
  const movement_assessments = db.prepare('SELECT * FROM movement_assessments WHERE user_id = ? ORDER BY assessment_date DESC').all(userId);
  const activity_records = db.prepare('SELECT * FROM activity_records WHERE user_id = ? ORDER BY record_date DESC LIMIT 30').all(userId);
  const meal_logs = db.prepare('SELECT * FROM meal_logs WHERE user_id = ? ORDER BY logged_at DESC LIMIT 50').all(userId);
  const sleep_records = db.prepare('SELECT * FROM sleep_records WHERE user_id = ? ORDER BY record_date DESC LIMIT 30').all(userId);
  const behaviour_records = db.prepare('SELECT * FROM behaviour_records WHERE user_id = ? ORDER BY record_date DESC LIMIT 50').all(userId);
  const completed_activities = db.prepare(`
    SELECT ac.*, pa.activity_title, pa.specialist_name 
    FROM activity_completions ac
    JOIN plan_activities pa ON ac.plan_activity_id = pa.id
    WHERE ac.user_id = ? ORDER BY ac.completed_at DESC LIMIT 20
  `).all(userId);
  const latestPlan = db.prepare('SELECT * FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(userId);

  // Parse JSON fields
  if (profile) {
    const jsonFields = ['wellness_goals', 'activity_preferences', 'exercise_types', 'food_preferences', 'food_restrictions', 'allergies'];
    for (const field of jsonFields) {
      if (profile[field] && typeof profile[field] === 'string') {
        try { profile[field] = JSON.parse(profile[field]); } catch { /* keep as string */ }
      }
    }
  }

  return {
    user,
    profile,
    health_screening,
    movement_assessments,
    activity_records,
    meal_logs,
    sleep_records,
    behaviour_records,
    history: {
      completed_activities,
      latest_plan: latestPlan
    }
  };
}

/**
 * Persists specialist execution record and its recommendations.
 */
function persistSpecialistResult(db, userId, workflowId, result) {
  const execId = uuidv4();

  db.prepare(`
    INSERT INTO specialist_executions (id, user_id, workflow_id, specialist_name, input_json, output_json, execution_status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(
    execId, userId, workflowId, result.specialist,
    JSON.stringify({ userId }),
    JSON.stringify(result),
    result.status || 'COMPLETED'
  );

  const insertRec = db.prepare(`
    INSERT INTO specialist_recommendations (id, user_id, workflow_id, specialist_name, recommendation_title, recommendation_description, priority, recommendation_type, evidence_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  for (const rec of (result.recommendations || [])) {
    insertRec.run(
      uuidv4(), userId, workflowId, result.specialist,
      rec.title, rec.description,
      rec.priority || 'MEDIUM',
      rec.type || null,
      JSON.stringify(result.metrics || {})
    );
  }
}

/**
 * Persists the health plan and its activities.
 */
function persistHealthPlan(db, userId, workflowId, planDate, allResults, overallScore, summary) {
  const planId = uuidv4();

  db.prepare(`
    INSERT INTO health_plans (id, user_id, workflow_id, plan_date, summary, overall_score)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(planId, userId, workflowId, planDate, summary, overallScore);

  const insertActivity = db.prepare(`
    INSERT INTO plan_activities (id, plan_id, specialist_name, activity_title, description, instructions, time_block, duration_minutes, dosage, exercise_id, caution, activity_type, completion_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
  `);

  for (const result of allResults) {
    for (const activity of (result.activities || [])) {
      insertActivity.run(
        uuidv4(), planId, result.specialist,
        activity.activity_title,
        activity.description || null,
        activity.instructions || null,
        activity.time_block || 'ANYTIME',
        activity.duration_minutes || null,
        activity.dosage || null,
        activity.exercise_id || null,
        activity.caution || null,
        activity.activity_type || null
      );
    }
  }

  return planId;
}

/**
 * Calculates live, genuine MoveWell Score from SQLite records.
 * Components:
 * - Prescribed Exercise Adherence (40% weight): completed vs prescribed activities
 * - Kinematic Movement Assessment (30% weight): validated MoveNet shoulder & balance screen
 * - Daily Habit & Lifestyle Logging (15% weight): actual logged steps, sleep, meals, habits
 * - Baseline Clinical Clearance (15% weight): profile & health screening safety clearance
 */
export function calculateLiveMoveWellScore(userId) {
  const db = getDb();

  // 1. Prescribed Exercise Adherence (40%)
  const latestPlan = db.prepare('SELECT id FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(userId);
  let exerciseAdherenceScore = 0;
  let totalPlanActs = 0;
  let completedPlanActs = 0;

  if (latestPlan) {
    totalPlanActs = db.prepare('SELECT COUNT(*) as c FROM plan_activities WHERE plan_id = ?').get(latestPlan.id).c;
    completedPlanActs = db.prepare(`
      SELECT COUNT(*) as c FROM activity_completions ac
      JOIN plan_activities pa ON ac.plan_activity_id = pa.id
      WHERE pa.plan_id = ? AND ac.user_id = ?
    `).get(latestPlan.id, userId).c;

    if (totalPlanActs > 0) {
      exerciseAdherenceScore = Math.round((completedPlanActs / totalPlanActs) * 100);
    }
  }

  // 2. Kinematic Movement Assessments (30%)
  const assessments = db.prepare('SELECT assessment_type, left_measurement, right_measurement FROM movement_assessments WHERE user_id = ?').all(userId);
  let assessmentScore = 0;
  const shoulder = assessments.find(a => a.assessment_type === 'SHOULDER_RAISE');
  const balance = assessments.find(a => a.assessment_type === 'ONE_LEG_STAND');

  if (shoulder || balance) {
    let sScore = 70;
    if (shoulder) {
      const diff = Math.abs((shoulder.left_measurement || 0) - (shoulder.right_measurement || 0));
      sScore = Math.max(50, Math.min(100, 95 - diff * 2));
    }
    let bScore = 70;
    if (balance) {
      const diff = Math.abs((balance.left_measurement || 0) - (balance.right_measurement || 0));
      bScore = Math.max(50, Math.min(100, 95 - diff * 2.5));
    }
    assessmentScore = Math.round(shoulder && balance ? (sScore + bScore) / 2 : (shoulder ? sScore : bScore));
  }

  // 3. Daily Logging Activity (15%)
  const today = new Date().toISOString().substring(0, 10);
  const stepsToday = db.prepare('SELECT id FROM activity_records WHERE user_id = ? AND record_date = ?').get(userId, today);
  const sleepToday = db.prepare('SELECT id FROM sleep_records WHERE user_id = ? AND record_date = ?').get(userId, today);
  const mealsToday = db.prepare('SELECT id FROM meal_logs WHERE user_id = ? AND date(logged_at) = ?').get(userId, today);
  const habitsToday = db.prepare('SELECT id FROM behaviour_records WHERE user_id = ? AND record_date = ?').get(userId, today);

  const loggedCount = (stepsToday ? 1 : 0) + (sleepToday ? 1 : 0) + (mealsToday ? 1 : 0) + (habitsToday ? 1 : 0);
  const loggingScore = Math.round((loggedCount / 4) * 100);

  // 4. Clinical Safety Gate & Baseline Screening (15%)
  const screening = db.prepare('SELECT * FROM health_screenings WHERE user_id = ? ORDER BY completed_at DESC LIMIT 1').get(userId);
  const profile = db.prepare('SELECT * FROM user_profiles WHERE user_id = ?').get(userId);
  let baselineScore = 0;
  if (profile) baselineScore += 40;
  if (screening) {
    const isCleared = screening.heart_condition === 'NO' && screening.hypertension === 'NO';
    baselineScore += isCleared ? 60 : 30;
  }

  // Calculate Weighted MoveWell Composite Score
  const overallScore = Math.round(
    (exerciseAdherenceScore * 0.40) +
    (assessmentScore * 0.30) +
    (loggingScore * 0.15) +
    (baselineScore * 0.15)
  );

  return {
    overall_score: overallScore,
    breakdown: {
      exercise_adherence: { score: exerciseAdherenceScore, weight: '40%', completed: completedPlanActs, total: totalPlanActs },
      kinematic_assessment: { score: assessmentScore, weight: '30%', assessed: !!(shoulder || balance) },
      daily_logging: { score: loggingScore, weight: '15%', logged_today: loggedCount },
      clinical_baseline: { score: baselineScore, weight: '15%', completed: !!(profile && screening) }
    }
  };
}

/**
 * Main orchestrator: runs all six specialists, persists results, returns full plan.
 */
export async function runWorkflow(userId) {
  const db = getDb();
  const workflowId = uuidv4();
  
  // Tomorrow's date as default local calendar plan date
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const planDate = tomorrow.toISOString().substring(0, 10);

  // Load all user context once (single source of truth)
  const userContext = loadUserContext(userId);

  // Run all six specialist agents
  const physiotherapyResult = runPhysiotherapyAgent(userContext);
  const nutritionResult = runNutritionAgent(userContext);
  const behaviourResult = runBehaviourAgent(userContext);
  const recoveryResult = runRecoveryAgent(userContext);
  const activityResult = runActivityAgent(userContext);
  const progressResult = runProgressAgent(userContext);

  const allResults = [
    physiotherapyResult,
    nutritionResult,
    behaviourResult,
    recoveryResult,
    activityResult,
    progressResult
  ];

  // Persist all results in a transaction
  const persistAll = db.transaction(() => {
    for (const result of allResults) {
      persistSpecialistResult(db, userId, workflowId, result);
    }

    const { overall_score: overallScore } = calculateLiveMoveWellScore(userId);

    const summaryParts = allResults.map(r => r.summary).filter(Boolean);
    const planSummary = `MoveWell daily plan generated. ${summaryParts.slice(0, 3).join(' ')}`;

    const planId = persistHealthPlan(db, userId, workflowId, planDate, allResults, overallScore, planSummary);

    // Save to workflow_history if exists
    try {
      db.prepare(`
        INSERT INTO workflow_history (id, user_id, workflow_id, executed_at, overall_score)
        VALUES (?, ?, ?, datetime('now'), ?)
      `).run(uuidv4(), userId, workflowId, overallScore);
    } catch {
      // ignore if table not created yet
    }

    return { planId, overallScore, planSummary };
  });

  const { planId, overallScore, planSummary } = persistAll();

  // Fetch persisted plan activities
  const planActivities = db.prepare(`
    SELECT pa.*, e.name as exercise_name, e.image_url, e.video_url, e.instructions as exercise_instructions,
           e.sets, e.reps, e.hold_duration, e.breathing, e.common_mistakes, e.safety_precautions, e.easier_variation
    FROM plan_activities pa
    LEFT JOIN exercise_catalogue e ON e.id = pa.exercise_id
    WHERE pa.plan_id = ?
    ORDER BY 
      CASE pa.time_block
        WHEN 'MORNING' THEN 1
        WHEN 'WORK_DAY' THEN 2
        WHEN 'AFTERNOON' THEN 3
        WHEN 'EVENING' THEN 4
        ELSE 5
      END,
      pa.specialist_name
  `).all(planId);

  // Aggregate all recommendations
  const allRecommendations = db.prepare(`
    SELECT * FROM specialist_recommendations WHERE workflow_id = ? ORDER BY priority, specialist_name
  `).all(workflowId);

  return {
    workflow_id: workflowId,
    plan_id: planId,
    plan_date: planDate,
    overall_score: overallScore,
    summary: planSummary,
    specialists: allResults.map(r => ({
      name: r.specialist,
      status: r.status,
      summary: r.summary,
      findings: r.findings || null,
      metrics: r.metrics || null,
      activity_score: r.activity_score || null,
      safety_approved: r.safety_approved,
      unknown_fields: r.unknown_fields || [],
      movewell_contribution: r.movewell_contribution
    })),
    recommendations: allRecommendations,
    plan_activities: planActivities,
    context_snapshot: {
      has_profile: !!userContext.profile,
      has_health_screening: !!userContext.health_screening,
      assessment_count: (userContext.movement_assessments || []).length,
      activity_days_logged: (userContext.activity_records || []).length,
      meal_log_days: new Set((userContext.meal_logs || []).map(m => m.logged_at?.substring(0, 10))).size,
      sleep_days_logged: (userContext.sleep_records || []).length,
      behaviour_days_logged: new Set((userContext.behaviour_records || []).map(b => b.record_date)).size
    }
  };
}

/**
 * Fetches the latest health plan for a user.
 */
export function getLatestPlan(userId) {
  const db = getDb();

  const plan = db.prepare(`
    SELECT * FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
  `).get(userId);

  if (!plan) return null;

  const activities = db.prepare(`
    SELECT pa.*, e.name as exercise_name, e.image_url, e.video_url, e.instructions as exercise_instructions,
           e.sets, e.reps, e.hold_duration, e.breathing, e.common_mistakes, e.safety_precautions, e.easier_variation
    FROM plan_activities pa
    LEFT JOIN exercise_catalogue e ON e.id = pa.exercise_id
    WHERE pa.plan_id = ?
    ORDER BY 
      CASE pa.time_block
        WHEN 'MORNING' THEN 1
        WHEN 'WORK_DAY' THEN 2
        WHEN 'AFTERNOON' THEN 3
        WHEN 'EVENING' THEN 4
        ELSE 5
      END,
      pa.specialist_name
  `).all(plan.id);

  const recommendations = db.prepare(`
    SELECT * FROM specialist_recommendations WHERE workflow_id = ? ORDER BY priority, specialist_name
  `).all(plan.workflow_id);

  const specialists = db.prepare(`
    SELECT specialist_name, execution_status, output_json FROM specialist_executions WHERE workflow_id = ?
  `).all(plan.workflow_id);

  const assessments = db.prepare(`
    SELECT * FROM movement_assessments WHERE user_id = ? ORDER BY assessment_date DESC LIMIT 5
  `).all(userId);

  const screening = db.prepare(`
    SELECT * FROM health_screenings WHERE user_id = ? ORDER BY completed_at DESC LIMIT 1
  `).get(userId);

  const liveScore = calculateLiveMoveWellScore(userId);
  plan.overall_score = liveScore.overall_score;

  return {
    plan,
    activities,
    recommendations,
    specialists,
    assessments,
    screening,
    movewell_score: liveScore.overall_score,
    score_breakdown: liveScore.breakdown
  };
}
