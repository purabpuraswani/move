import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';
import { calculateLiveMoveWellScore } from '../orchestrator/workflowOrchestrator.js';

const router = express.Router();

// GET /api/activity - All activity records
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const records = db.prepare(`
      SELECT * FROM activity_records WHERE user_id = ? ORDER BY record_date DESC LIMIT 30
    `).all(req.userId);

    const latest = records[0] || null;
    const profile = db.prepare('SELECT daily_steps, sitting_hours, movement_breaks, exercise_frequency, exercise_minutes FROM user_profiles WHERE user_id = ?').get(req.userId);

    // Calculate score
    const steps = latest?.daily_steps ?? profile?.daily_steps ?? null;
    const sitting = latest?.sitting_hours ?? profile?.sitting_hours ?? null;
    const breaks = latest?.movement_breaks ?? profile?.movement_breaks ?? null;
    const freq = profile?.exercise_frequency ?? null;
    const minutes = profile?.exercise_minutes ?? null;

    let score = null;
    if (steps !== null || sitting !== null || freq !== null) {
      const sScore = steps !== null ? Math.min(100, (steps / 10000) * 100) : null;
      const fScore = freq !== null ? Math.min(100, (freq / 7) * 100) : null;
      const dScore = freq !== null && minutes !== null ? Math.min(100, ((freq * minutes) / 300) * 100) : null;
      const sitScore = sitting !== null ? Math.max(0, 100 - Math.max(0, sitting - 4) * 20) : null;
      const bScore = breaks !== null ? Math.min(100, (breaks / 6) * 100) : null;

      const comps = [
        { score: sScore, weight: 0.30, label: 'Daily Steps', value: steps },
        { score: fScore, weight: 0.20, label: 'Exercise Frequency', value: freq },
        { score: dScore, weight: 0.20, label: 'Exercise Duration', value: freq && minutes ? freq * minutes : null },
        { score: sitScore, weight: 0.20, label: 'Sitting Duration', value: sitting },
        { score: bScore, weight: 0.10, label: 'Movement Breaks', value: breaks }
      ];

      const avail = comps.filter(c => c.score !== null);
      if (avail.length > 0) {
        const totalW = avail.reduce((s, c) => s + c.weight, 0);
        score = {
          overall: Math.round(avail.reduce((s, c) => s + (c.score * c.weight), 0) / totalW),
          components: comps
        };
      }
    }

    res.json({ records, latest, activity_score: score });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch activity records' });
  }
});

// POST /api/activity - Log new activity entry
router.post('/', authenticateToken, (req, res) => {
  const db = getDb();
  const { record_date, daily_steps, sitting_hours, movement_breaks, exercise_frequency, exercise_minutes, exercise_type, source } = req.body;

  const date = record_date || new Date().toISOString().substring(0, 10);
  const id = uuidv4();

  try {
    db.prepare(`
      INSERT INTO activity_records (id, user_id, record_date, daily_steps, sitting_hours, movement_breaks, exercise_frequency, exercise_minutes, exercise_type, source)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id, req.userId, date,
      daily_steps ?? null,
      sitting_hours ?? null,
      movement_breaks ?? null,
      exercise_frequency ?? null,
      exercise_minutes ?? null,
      exercise_type ?? null,
      source || 'manual'
    );

    // Also update profile daily_steps and sitting_hours if provided
    const updates = [];
    const vals = [];
    if (daily_steps != null) { updates.push('daily_steps = ?'); vals.push(daily_steps); }
    if (sitting_hours != null) { updates.push('sitting_hours = ?'); vals.push(sitting_hours); }
    if (movement_breaks != null) { updates.push('movement_breaks = ?'); vals.push(movement_breaks); }
    if (updates.length > 0) {
      vals.push(req.userId);
      db.prepare(`UPDATE user_profiles SET ${updates.join(', ')} WHERE user_id = ?`).run(...vals);
    }

    const created = db.prepare('SELECT * FROM activity_records WHERE id = ?').get(id);
    res.status(201).json(created);
  } catch (err) {
    console.error('Activity log error:', err);
    res.status(500).json({ error: 'Failed to log activity record' });
  }
});

// POST /api/activity/complete - Complete plan activity
router.post('/complete', authenticateToken, (req, res) => {
  const db = getDb();
  const { plan_activity_id, notes } = req.body;

  if (!plan_activity_id) {
    return res.status(400).json({ error: 'plan_activity_id is required' });
  }

  try {
    const activity = db.prepare('SELECT * FROM plan_activities WHERE id = ?').get(plan_activity_id);
    if (!activity) return res.status(404).json({ error: 'Plan activity not found' });

    const completionId = uuidv4();

    db.transaction(() => {
      // Update plan activity status
      db.prepare("UPDATE plan_activities SET completion_status = 'COMPLETED' WHERE id = ?").run(plan_activity_id);

      // Insert completion record
      db.prepare(`
        INSERT INTO activity_completions (id, user_id, plan_activity_id, completion_status, completed_at, notes)
        VALUES (?, ?, ?, 'COMPLETED', datetime('now'), ?)
      `).run(completionId, req.userId, plan_activity_id, notes || `Completed ${activity.activity_title}`);

      // Insert progress record
      db.prepare(`
        INSERT INTO progress_records (id, user_id, record_type, metric_name, metric_value, metric_unit, source, record_date)
        VALUES (?, ?, 'PLAN_ACTIVITY_COMPLETION', ?, 1, 'activity', ?, date('now'))
      `).run(uuidv4(), req.userId, activity.activity_title, activity.specialist_name);
    })();

    // Recalculate live MoveWell score and update active plan
    const liveScore = calculateLiveMoveWellScore(req.userId);
    try {
      db.prepare(`
        UPDATE health_plans SET overall_score = ?
        WHERE id = (SELECT plan_id FROM plan_activities WHERE id = ?)
      `).run(liveScore.overall_score, plan_activity_id);
    } catch { /* non-fatal */ }

    res.json({
      success: true,
      message: `Completed ${activity.activity_title}`,
      completion_id: completionId,
      new_overall_score: liveScore.overall_score,
      score_breakdown: liveScore.breakdown
    });
  } catch (err) {
    console.error('Plan activity complete error:', err);
    res.status(500).json({ error: 'Failed to record activity completion' });
  }
});

// PATCH /api/activity/complete/:id - Update completion status
router.patch('/complete/:id', authenticateToken, (req, res) => {
  const db = getDb();
  const { status, notes } = req.body;

  try {
    db.prepare(`
      UPDATE activity_completions 
      SET completion_status = ?, notes = coalesce(?, notes)
      WHERE id = ? AND user_id = ?
    `).run(status || 'COMPLETED', notes || null, req.params.id, req.userId);

    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to update completion record' });
  }
});

export default router;
