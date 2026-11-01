import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

// GET all assessments for user
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const assessments = db.prepare(`
      SELECT * FROM movement_assessments WHERE user_id = ? ORDER BY assessment_date DESC
    `).all(req.userId);
    res.json(assessments);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch assessments' });
  }
});

// GET assessment by ID
router.get('/:id', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const assessment = db.prepare(`
      SELECT * FROM movement_assessments WHERE id = ? AND user_id = ?
    `).get(req.params.id, req.userId);
    if (!assessment) return res.status(404).json({ error: 'Assessment not found' });
    res.json(assessment);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch assessment' });
  }
});

// POST new assessment
router.post('/', authenticateToken, (req, res) => {
  const { assessment_type, left_measurement, right_measurement, unit, result_json, status, source } = req.body;
  if (!assessment_type) {
    return res.status(400).json({ error: 'assessment_type is required' });
  }

  const db = getDb();
  try {
    const id = uuidv4();
    db.prepare(`
      INSERT INTO movement_assessments (id, user_id, assessment_type, left_measurement, right_measurement, unit, result_json, source, assessment_date, status)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
    `).run(
      id,
      req.userId,
      assessment_type,
      left_measurement !== undefined ? left_measurement : null,
      right_measurement !== undefined ? right_measurement : null,
      unit || (assessment_type === 'SHOULDER_RAISE' ? 'degrees' : 'seconds'),
      typeof result_json === 'object' ? JSON.stringify(result_json) : result_json || null,
      source || 'camera',
      status || 'COMPLETED'
    );

    const created = db.prepare('SELECT * FROM movement_assessments WHERE id = ?').get(id);
    res.status(201).json(created);
  } catch (err) {
    console.error('Assessment creation error:', err);
    res.status(500).json({ error: 'Failed to save assessment' });
  }
});

export default router;

