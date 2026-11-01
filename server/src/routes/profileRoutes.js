import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';
import { loadUserContext, runWorkflow } from '../orchestrator/workflowOrchestrator.js';

const router = express.Router();

// GET profile
router.get('/', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const profile = db.prepare('SELECT * FROM user_profiles WHERE user_id = ?').get(req.userId);
    const screening = db.prepare('SELECT * FROM health_screenings WHERE user_id = ? ORDER BY completed_at DESC LIMIT 1').get(req.userId);
    res.json({ profile, health_screening: screening });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch profile' });
  }
});

// PUT / PATCH profile
const updateProfile = async (req, res) => {
  const db = getDb();
  const fields = { ...req.body };

  // Unpack health_conditions if nested
  if (fields.health_conditions && typeof fields.health_conditions === 'object') {
    Object.assign(fields, fields.health_conditions);
  }

  // Map common frontend aliases
  if (fields.height_cm !== undefined && fields.height === undefined) fields.height = fields.height_cm;
  if (fields.weight_kg !== undefined && fields.weight === undefined) fields.weight = fields.weight_kg;
  if (fields.daily_steps_goal !== undefined && fields.daily_steps === undefined) fields.daily_steps = fields.daily_steps_goal;
  if (fields.water_intake_litres !== undefined && fields.water_intake_liters === undefined) fields.water_intake_liters = fields.water_intake_litres;
  if (fields.dietary_restrictions !== undefined && fields.food_restrictions === undefined) fields.food_restrictions = fields.dietary_restrictions;

  try {
    // Ensure user_profiles row exists
    let existingProfile = db.prepare('SELECT id FROM user_profiles WHERE user_id = ?').get(req.userId);
    if (!existingProfile) {
      db.prepare(`
        INSERT INTO user_profiles (id, user_id, onboarding_completed)
        VALUES (?, ?, 0)
      `).run(uuidv4(), req.userId);
    }

    // Ensure health_screenings row exists
    let existingScreening = db.prepare('SELECT id FROM health_screenings WHERE user_id = ?').get(req.userId);
    if (!existingScreening) {
      db.prepare(`
        INSERT INTO health_screenings (id, user_id)
        VALUES (?, ?)
      `).run(uuidv4(), req.userId);
    }

    const allowedProfile = [
      'date_of_birth', 'height', 'weight', 'work_pattern', 'wellness_goals',
      'activity_preferences', 'food_preferences', 'food_restrictions', 'allergies',
      'water_intake_liters', 'fruit_veg_servings', 'sleep_hours', 'sleep_quality',
      'stress_level', 'motivation', 'barriers', 'existing_habits', 'preferred_changes',
      'nutrition_goals', 'daily_steps', 'exercise_frequency', 'exercise_minutes',
      'sitting_hours', 'movement_breaks', 'exercise_types', 'onboarding_completed'
    ];

    const updates = [];
    const values = [];

    for (const key of allowedProfile) {
      if (fields[key] !== undefined) {
        updates.push(`${key} = ?`);
        let val = fields[key];

        // Sanitize SQLite data types
        if (typeof val === 'boolean') {
          val = val ? 1 : 0;
        } else if (typeof val === 'object' && val !== null) {
          val = JSON.stringify(val);
        } else if (val === '' || val === undefined) {
          val = null;
        }

        values.push(val);
      }
    }

    if (updates.length > 0) {
      updates.push("updated_at = datetime('now')");
      values.push(req.userId);
      db.prepare(`UPDATE user_profiles SET ${updates.join(', ')} WHERE user_id = ?`).run(...values);
    }

    // Health screening fields
    const screeningFields = [
      'diabetes', 'hypertension', 'heart_condition', 'injury_history',
      'joint_pain', 'back_pain', 'neck_pain', 'other_conditions'
    ];

    const sUpdates = [];
    const sValues = [];
    for (const key of screeningFields) {
      if (fields[key] !== undefined) {
        sUpdates.push(`${key} = ?`);
        let val = fields[key];
        if (typeof val === 'boolean') {
          val = val ? 'YES' : 'NO';
        } else if (val === '' || val === undefined) {
          val = 'UNKNOWN';
        }
        sValues.push(val);
      }
    }

    if (sUpdates.length > 0) {
      sUpdates.push("completed_at = datetime('now')");
      sValues.push(req.userId);
      db.prepare(`UPDATE health_screenings SET ${sUpdates.join(', ')} WHERE user_id = ?`).run(...sValues);
    }

    // If onboarding just completed, run workflow to generate initial plan!
    if (fields.onboarding_completed) {
      try {
        await runWorkflow(req.userId);
      } catch (wfErr) {
        console.warn('Post-onboarding workflow error (non-fatal):', wfErr);
      }
    }

    const updatedProfile = db.prepare('SELECT * FROM user_profiles WHERE user_id = ?').get(req.userId);
    const updatedScreening = db.prepare('SELECT * FROM health_screenings WHERE user_id = ? ORDER BY completed_at DESC LIMIT 1').get(req.userId);

    res.json({ profile: updatedProfile, health_screening: updatedScreening });
  } catch (err) {
    console.error('Profile update error:', err);
    res.status(500).json({ error: 'Failed to update profile' });
  }
};

router.put('/', authenticateToken, updateProfile);
router.patch('/', authenticateToken, updateProfile);

// GET /wellness (full unified context)
router.get('/wellness', authenticateToken, (req, res) => {
  try {
    const context = loadUserContext(req.userId);
    res.json(context);
  } catch (err) {
    res.status(500).json({ error: 'Failed to load user wellness context' });
  }
});

export default router;
