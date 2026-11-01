import express from 'express';
import { runWorkflow, getLatestPlan } from '../orchestrator/workflowOrchestrator.js';
import { authenticateToken } from '../middleware/auth.js';
import { getDb } from '../database/connection.js';

const router = express.Router();

// POST /api/workflow/run - Run all six specialists and generate unified plan
router.post('/run', authenticateToken, async (req, res) => {
  try {
    const result = await runWorkflow(req.userId);
    res.json(result);
  } catch (err) {
    console.error('Workflow execution error:', err);
    res.status(500).json({ error: 'Failed to run wellness workflow', details: err.message });
  }
});

// GET /api/workflow/:id - Get specific workflow run details
router.get('/:id', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const executions = db.prepare(`
      SELECT * FROM specialist_executions WHERE workflow_id = ? AND user_id = ?
    `).all(req.params.id, req.userId);

    const plan = db.prepare(`
      SELECT * FROM health_plans WHERE workflow_id = ? AND user_id = ?
    `).get(req.params.id, req.userId);

    const recommendations = db.prepare(`
      SELECT * FROM specialist_recommendations WHERE workflow_id = ? AND user_id = ?
    `).all(req.params.id, req.userId);

    res.json({ executions, plan, recommendations });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch workflow details' });
  }
});

export default router;

