import express from 'express';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

// GET all specialists latest status & findings
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const latestPlan = db.prepare(`
      SELECT workflow_id FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
    `).get(req.userId);

    if (!latestPlan) {
      return res.json([]);
    }

    const executions = db.prepare(`
      SELECT * FROM specialist_executions 
      WHERE workflow_id = ? AND user_id = ?
    `).all(latestPlan.workflow_id, req.userId);

    const parsed = executions.map(e => ({
      ...e,
      output: e.output_json ? JSON.parse(e.output_json) : null
    }));

    res.json(parsed);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch specialists' });
  }
});

// GET specific specialist details
router.get('/:name', authenticateToken, (req, res) => {
  const db = getDb();
  const name = req.params.name.toUpperCase();

  try {
    const execution = db.prepare(`
      SELECT * FROM specialist_executions 
      WHERE user_id = ? AND specialist_name = ?
      ORDER BY created_at DESC LIMIT 1
    `).get(req.userId, name);

    if (!execution) return res.status(404).json({ error: `Specialist ${name} not found or not executed yet` });

    const recommendations = db.prepare(`
      SELECT * FROM specialist_recommendations 
      WHERE user_id = ? AND specialist_name = ?
      ORDER BY created_at DESC LIMIT 20
    `).all(req.userId, name);

    res.json({
      ...execution,
      output: execution.output_json ? JSON.parse(execution.output_json) : null,
      recommendations
    });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch specialist details' });
  }
});

// GET specialist history
router.get('/:name/history', authenticateToken, (req, res) => {
  const db = getDb();
  const name = req.params.name.toUpperCase();

  try {
    const history = db.prepare(`
      SELECT * FROM specialist_executions 
      WHERE user_id = ? AND specialist_name = ?
      ORDER BY created_at DESC LIMIT 30
    `).all(req.userId, name);

    const parsed = history.map(h => ({
      ...h,
      output: h.output_json ? JSON.parse(h.output_json) : null
    }));

    res.json(parsed);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch specialist history' });
  }
});

export default router;

