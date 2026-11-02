import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';
import { handleRecoveryVoiceConversation } from '../services/recoveryVoiceAgent.js';

const router = express.Router();

// GET /api/recovery - Sleep & recovery records
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const records = db.prepare(`
      SELECT * FROM sleep_records WHERE user_id = ? ORDER BY record_date DESC LIMIT 30
    `).all(req.userId);

    const profile = db.prepare('SELECT sleep_hours, sleep_quality, stress_level FROM user_profiles WHERE user_id = ?').get(req.userId);
    res.json({ records, profile });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch recovery records' });
  }
});

// POST /api/recovery/chat - Conversational voice & text agent powered by Gemini
router.post('/chat', authenticateToken, async (req, res) => {
  const { message, conversationHistory } = req.body;
  if (!message) {
    return res.status(400).json({ error: 'Message is required' });
  }

  try {
    const result = await handleRecoveryVoiceConversation(req.userId, message, conversationHistory || []);
    res.json(result);
  } catch (err) {
    console.error('Recovery voice chat error:', err);
    res.status(500).json({ error: err.message || 'Failed to process conversation' });
  }
});

// POST /api/recovery - Log sleep & recovery
router.post('/', authenticateToken, (req, res) => {
  const db = getDb();
  const { sleep_duration, sleep_quality, stress_level, recovery_notes, record_date } = req.body;

  if (sleep_duration === undefined || !sleep_quality) {
    return res.status(400).json({ error: 'sleep_duration and sleep_quality are required' });
  }

  const date = record_date || new Date().toISOString().substring(0, 10);
  const id = uuidv4();

  try {
    db.prepare(`
      INSERT INTO sleep_records (id, user_id, sleep_duration, sleep_quality, stress_level, recovery_notes, record_date)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(id, req.userId, parseFloat(sleep_duration), sleep_quality, stress_level ? parseInt(stress_level) : null, recovery_notes || null, date);

    // Update profile
    db.prepare(`
      UPDATE user_profiles 
      SET sleep_hours = ?, sleep_quality = ?, stress_level = coalesce(?, stress_level), updated_at = datetime('now')
      WHERE user_id = ?
    `).run(parseFloat(sleep_duration), sleep_quality, stress_level ? parseInt(stress_level) : null, req.userId);

    const created = db.prepare('SELECT * FROM sleep_records WHERE id = ?').get(id);
    res.status(201).json(created);
  } catch (err) {
    console.error('Recovery log error:', err);
    res.status(500).json({ error: 'Failed to log recovery record' });
  }
});

export default router;
