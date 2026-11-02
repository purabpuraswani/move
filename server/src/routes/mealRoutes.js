import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';
import { handleNutritionVoiceConversation } from '../services/nutritionVoiceAgent.js';

const router = express.Router();

// GET /api/meals - Meal logs + scheduled meal plan activities
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const meals = db.prepare(`
      SELECT * FROM meal_logs WHERE user_id = ? ORDER BY logged_at DESC LIMIT 50
    `).all(req.userId);

    const profile = db.prepare(`
      SELECT water_intake_liters, fruit_veg_servings, food_preferences, food_restrictions, allergies, nutrition_goals
      FROM user_profiles WHERE user_id = ?
    `).get(req.userId);

    // Fetch scheduled meal plan activities from latest health plan
    const latestPlan = db.prepare('SELECT id FROM health_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(req.userId);
    let scheduledPlanMeals = [];
    if (latestPlan) {
      scheduledPlanMeals = db.prepare(`
        SELECT id, activity_title, description, instructions, time_block, dosage, caution, completion_status
        FROM plan_activities
        WHERE plan_id = ? AND specialist_name = 'NUTRITION'
        ORDER BY 
          CASE time_block
            WHEN 'MORNING' THEN 1
            WHEN 'AFTERNOON' THEN 2
            WHEN 'EVENING' THEN 3
            ELSE 4
          END
      `).all(latestPlan.id);
    }

    res.json({ meals, profile, scheduledPlanMeals });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch meal logs' });
  }
});

// POST /api/meals/chat - Conversational nutrition & meal scheduling agent powered by OpenRouter
router.post('/chat', authenticateToken, async (req, res) => {
  const { message, conversationHistory } = req.body;
  if (!message) {
    return res.status(400).json({ error: 'Message is required' });
  }

  try {
    const result = await handleNutritionVoiceConversation(req.userId, message, conversationHistory || []);
    res.json(result);
  } catch (err) {
    console.error('Nutrition voice chat error:', err);
    res.status(500).json({ error: err.message || 'Failed to process nutrition conversation' });
  }
});

// POST /api/meals - Log a meal
router.post('/', authenticateToken, (req, res) => {
  const db = getDb();
  const { meal_type, food_description, portion, calories_optional, notes } = req.body;

  if (!meal_type || !food_description) {
    return res.status(400).json({ error: 'meal_type and food_description are required' });
  }

  const id = uuidv4();
  try {
    db.prepare(`
      INSERT INTO meal_logs (id, user_id, meal_type, food_description, portion, calories_optional, notes, logged_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    `).run(id, req.userId, meal_type.toUpperCase(), food_description, portion || null, calories_optional ? parseInt(calories_optional) : null, notes || null);

    const created = db.prepare('SELECT * FROM meal_logs WHERE id = ?').get(id);
    res.status(201).json(created);
  } catch (err) {
    console.error('Meal log error:', err);
    res.status(500).json({ error: 'Failed to log meal' });
  }
});

// DELETE /api/meals/:id - Delete a meal log
router.delete('/:id', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const info = db.prepare('DELETE FROM meal_logs WHERE id = ? AND user_id = ?').run(req.params.id, req.userId);
    if (info.changes === 0) return res.status(404).json({ error: 'Meal log not found' });
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to delete meal log' });
  }
});

export default router;
