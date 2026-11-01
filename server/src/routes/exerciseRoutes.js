import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';
import { calculateLiveMoveWellScore } from '../orchestrator/workflowOrchestrator.js';

const router = express.Router();

// Helper to format exercise
function formatExercise(ex) {
  if (!ex) return null;
  return {
    ...ex,
    instructions: ex.instructions ? (typeof ex.instructions === 'string' ? JSON.parse(ex.instructions) : ex.instructions) : [],
    common_mistakes: ex.common_mistakes ? (typeof ex.common_mistakes === 'string' ? JSON.parse(ex.common_mistakes) : ex.common_mistakes) : [],
    safety_precautions: ex.safety_precautions ? (typeof ex.safety_precautions === 'string' ? JSON.parse(ex.safety_precautions) : ex.safety_precautions) : []
  };
}

// GET /api/exercises
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const exercises = db.prepare('SELECT * FROM exercise_catalogue ORDER BY name').all();
    res.json(exercises.map(formatExercise));
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch exercise catalogue' });
  }
});

// GET /api/exercises/:id
router.get('/:id', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const exercise = db.prepare('SELECT * FROM exercise_catalogue WHERE id = ?').get(req.params.id);
    if (!exercise) return res.status(404).json({ error: 'Exercise not found' });
    res.json(formatExercise(exercise));
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch exercise' });
  }
});

// POST /api/exercises/:id/complete
router.post('/:id/complete', authenticateToken, (req, res) => {
  const db = getDb();
  const { notes, repetitions, sets, duration_seconds, tracking_quality } = req.body;

  try {
    const exercise = db.prepare('SELECT id, name FROM exercise_catalogue WHERE id = ?').get(req.params.id);
    if (!exercise) return res.status(404).json({ error: 'Exercise not found in catalogue' });

    // Find any active plan activity with this exercise
    let activity = db.prepare(`
      SELECT pa.id, pa.plan_id FROM plan_activities pa
      JOIN health_plans hp ON hp.id = pa.plan_id
      WHERE hp.user_id = ? AND pa.exercise_id = ? AND pa.completion_status != 'COMPLETED'
      ORDER BY hp.created_at DESC LIMIT 1
    `).get(req.userId, req.params.id);

    // If not found in current plan, check for any plan activity for this exercise
    if (!activity) {
      activity = db.prepare(`
        SELECT pa.id, pa.plan_id FROM plan_activities pa
        JOIN health_plans hp ON hp.id = pa.plan_id
        WHERE hp.user_id = ? AND pa.exercise_id = ?
        ORDER BY hp.created_at DESC LIMIT 1
      `).get(req.userId, req.params.id);
    }

    // If still no activity, attach to user's latest plan or create one
    let actId;
    if (activity) {
      actId = activity.id;
    } else {
      let latestPlan = db.prepare('SELECT id FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(req.userId);
      let planId;
      if (!latestPlan) {
        planId = uuidv4();
        db.prepare(`
          INSERT INTO health_plans (id, user_id, workflow_id, plan_date, summary, overall_score)
          VALUES (?, ?, ?, date('now'), 'MoveWell Personal Plan', 50)
        `).run(planId, req.userId, uuidv4());
      } else {
        planId = latestPlan.id;
      }

      actId = uuidv4();
      db.prepare(`
        INSERT INTO plan_activities (id, plan_id, specialist_name, activity_title, description, instructions, time_block, duration_minutes, dosage, exercise_id, completion_status)
        VALUES (?, ?, 'PHYSIOTHERAPY', ?, 'Physical rehabilitation exercise', null, 'ANYTIME', 15, '1 set', ?, 'PENDING')
      `).run(actId, planId, exercise.name, exercise.id);
    }

    const completionId = uuidv4();
    const finalReps = parseInt(repetitions) || 1;
    const finalSets = parseInt(sets) || 1;
    const finalDuration = parseInt(duration_seconds) || 30;
    const quality = tracking_quality || 'MoveNet SinglePose Lightning Validated';

    const sessionMetadata = JSON.stringify({
      exercise_id: exercise.id,
      exercise_name: exercise.name,
      repetitions: finalReps,
      sets: finalSets,
      duration_seconds: finalDuration,
      tracking_quality: quality,
      note: notes || `Completed ${finalReps} verified repetitions of ${exercise.name}`
    });

    db.transaction(() => {
      // Mark plan activity as completed
      db.prepare("UPDATE plan_activities SET completion_status = 'COMPLETED' WHERE id = ?").run(actId);

      // Record completion
      db.prepare(`
        INSERT INTO activity_completions (id, user_id, plan_activity_id, completion_status, completed_at, notes)
        VALUES (?, ?, ?, 'COMPLETED', datetime('now'), ?)
      `).run(completionId, req.userId, actId, sessionMetadata);

      // Record in progress_records
      db.prepare(`
        INSERT INTO progress_records (id, user_id, record_type, metric_name, metric_value, metric_unit, source, record_date)
        VALUES (?, ?, 'EXERCISE_COMPLETION', ?, ?, 'repetitions', ?, date('now'))
      `).run(uuidv4(), req.userId, exercise.name, finalReps, quality);
    })();

    // Recalculate live MoveWell score and update plan
    const liveScore = calculateLiveMoveWellScore(req.userId);
    try {
      db.prepare(`
        UPDATE health_plans SET overall_score = ?
        WHERE id = (SELECT plan_id FROM plan_activities WHERE id = ?)
      `).run(liveScore.overall_score, actId);
    } catch { /* non-fatal */ }

    res.json({
      success: true,
      message: `Successfully saved ${finalReps} reps of ${exercise.name}`,
      completion_id: completionId,
      new_overall_score: liveScore.overall_score,
      score_breakdown: liveScore.breakdown
    });
  } catch (err) {
    console.error('Exercise complete error:', err);
    res.status(500).json({ error: err.message || 'Failed to record exercise completion' });
  }
});

export default router;

