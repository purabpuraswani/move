import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();

// GET /api/behaviour - Behaviour & habit records
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const records = db.prepare(`
      SELECT * FROM behaviour_records WHERE user_id = ? ORDER BY record_date DESC, habit_key ASC LIMIT 50
    `).all(req.userId);

    const profile = db.prepare(`
      SELECT motivation, barriers, existing_habits, preferred_changes, sitting_hours, movement_breaks
      FROM user_profiles WHERE user_id = ?
    `).get(req.userId);

    res.json({ records, profile });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch behaviour records' });
  }
});

// POST /api/behaviour - Log habit completion / status
router.post('/', authenticateToken, (req, res) => {
  const db = getDb();
  const { habit_key, habit_name, status, notes, record_date } = req.body;

  if (!habit_key || !habit_name || !status) {
    return res.status(400).json({ error: 'habit_key, habit_name, and status are required' });
  }

  const date = record_date || new Date().toISOString().substring(0, 10);
  const id = uuidv4();

  try {
    // Check if record exists for this date and habit
    const existing = db.prepare(`
      SELECT id FROM behaviour_records WHERE user_id = ? AND habit_key = ? AND record_date = ?
    `).get(req.userId, habit_key, date);

    if (existing) {
      db.prepare(`
        UPDATE behaviour_records SET status = ?, notes = coalesce(?, notes) WHERE id = ?
      `).run(status, notes || null, existing.id);
      const updated = db.prepare('SELECT * FROM behaviour_records WHERE id = ?').get(existing.id);
      return res.json(updated);
    }

    db.prepare(`
      INSERT INTO behaviour_records (id, user_id, habit_key, habit_name, status, notes, record_date)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(id, req.userId, habit_key, habit_name, status, notes || null, date);

    const created = db.prepare('SELECT * FROM behaviour_records WHERE id = ?').get(id);
    res.status(201).json(created);
  } catch (err) {
    console.error('Habit log error:', err);
    res.status(500).json({ error: 'Failed to log habit record' });
  }
});

export default router;

