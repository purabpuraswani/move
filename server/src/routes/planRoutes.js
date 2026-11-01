import express from 'express';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';
import { getLatestPlan } from '../orchestrator/workflowOrchestrator.js';

const router = express.Router();

// GET /api/plans/current - Latest unified plan
router.get('/current', authenticateToken, (req, res) => {
  try {
    const data = getLatestPlan(req.userId);
    if (!data) return res.status(404).json({ error: 'No health plan generated yet' });
    res.json(data);
  } catch (err) {
    console.error('Plan fetch error:', err);
    res.status(500).json({ error: 'Failed to fetch current plan' });
  }
});

// GET /api/plans/history - All historical plans
router.get('/history', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const plans = db.prepare(`
      SELECT * FROM health_plans WHERE user_id = ? ORDER BY created_at DESC
    `).all(req.userId);
    res.json(plans);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch plan history' });
  }
});

// GET /api/plans/:id - Get specific plan with activities
router.get('/:id', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const plan = db.prepare(`
      SELECT * FROM health_plans WHERE id = ? AND user_id = ?
    `).get(req.params.id, req.userId);

    if (!plan) return res.status(404).json({ error: 'Plan not found' });

    const activities = db.prepare(`
      SELECT pa.*, e.name as exercise_name, e.image_url, e.video_url, e.instructions as exercise_instructions,
             e.sets, e.reps, e.hold_duration, e.breathing, e.common_mistakes, e.safety_precautions, e.easier_variation
      FROM plan_activities pa
      LEFT JOIN exercise_catalogue e ON e.id = pa.exercise_id
      WHERE pa.plan_id = ?
      ORDER BY pa.time_block, pa.specialist_name
    `).all(plan.id);

    const recommendations = db.prepare(`
      SELECT * FROM specialist_recommendations WHERE workflow_id = ? ORDER BY priority, specialist_name
    `).all(plan.workflow_id);

    res.json({ plan, activities, recommendations });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch plan' });
  }
});

export default router;

