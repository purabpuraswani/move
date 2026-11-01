import { getDb } from './connection.js';

export function initializeDatabase() {
  const db = getDb();

  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS user_profiles (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL UNIQUE,
      date_of_birth TEXT,
      height REAL,
      weight REAL,
      work_pattern TEXT,
      wellness_goals TEXT,
      activity_preferences TEXT,
      food_preferences TEXT,
      food_restrictions TEXT,
      allergies TEXT,
      water_intake_liters REAL,
      fruit_veg_servings INTEGER,
      sleep_hours REAL,
      sleep_quality TEXT,
      stress_level INTEGER,
      motivation TEXT,
      barriers TEXT,
      existing_habits TEXT,
      preferred_changes TEXT,
      nutrition_goals TEXT,
      daily_steps INTEGER,
      exercise_frequency INTEGER,
      exercise_minutes INTEGER,
      sitting_hours REAL,
      movement_breaks INTEGER,
      exercise_types TEXT,
      onboarding_completed INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS health_screenings (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      diabetes TEXT DEFAULT 'UNKNOWN',
      hypertension TEXT DEFAULT 'UNKNOWN',
      heart_condition TEXT DEFAULT 'UNKNOWN',
      injury_history TEXT DEFAULT 'UNKNOWN',
      joint_pain TEXT DEFAULT 'UNKNOWN',
      back_pain TEXT DEFAULT 'UNKNOWN',
      neck_pain TEXT DEFAULT 'UNKNOWN',
      other_conditions TEXT,
      completed_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS movement_assessments (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      assessment_type TEXT NOT NULL,
      left_measurement REAL,
      right_measurement REAL,
      unit TEXT DEFAULT 'degrees',
      result_json TEXT,
      source TEXT DEFAULT 'camera',
      assessment_date TEXT DEFAULT (datetime('now')),
      status TEXT DEFAULT 'COMPLETED',
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS activity_records (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      record_date TEXT NOT NULL,
      daily_steps INTEGER,
      sitting_hours REAL,
      movement_breaks INTEGER,
      exercise_frequency INTEGER,
      exercise_minutes INTEGER,
      exercise_type TEXT,
      source TEXT DEFAULT 'manual',
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS meal_logs (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      meal_type TEXT NOT NULL,
      food_description TEXT NOT NULL,
      portion TEXT,
      calories_optional INTEGER,
      notes TEXT,
      logged_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS sleep_records (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      sleep_duration REAL NOT NULL,
      sleep_quality TEXT NOT NULL,
      stress_level INTEGER,
      recovery_notes TEXT,
      record_date TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS behaviour_records (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      habit_key TEXT NOT NULL,
      habit_name TEXT NOT NULL,
      status TEXT NOT NULL,
      notes TEXT,
      record_date TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS specialist_executions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      workflow_id TEXT NOT NULL,
      specialist_name TEXT NOT NULL,
      input_json TEXT,
      output_json TEXT,
      execution_status TEXT DEFAULT 'PENDING',
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS specialist_recommendations (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      workflow_id TEXT NOT NULL,
      specialist_name TEXT NOT NULL,
      recommendation_title TEXT NOT NULL,
      recommendation_description TEXT NOT NULL,
      priority TEXT DEFAULT 'MEDIUM',
      recommendation_type TEXT,
      evidence_json TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS health_plans (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      workflow_id TEXT NOT NULL,
      plan_date TEXT NOT NULL,
      summary TEXT,
      overall_score REAL,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS plan_activities (
      id TEXT PRIMARY KEY,
      plan_id TEXT NOT NULL,
      specialist_name TEXT NOT NULL,
      activity_title TEXT NOT NULL,
      description TEXT,
      instructions TEXT,
      time_block TEXT,
      duration_minutes INTEGER,
      dosage TEXT,
      exercise_id TEXT,
      caution TEXT,
      activity_type TEXT,
      completion_status TEXT DEFAULT 'PENDING',
      FOREIGN KEY (plan_id) REFERENCES health_plans(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS activity_completions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      plan_activity_id TEXT NOT NULL,
      completion_status TEXT NOT NULL,
      completed_at TEXT DEFAULT (datetime('now')),
      notes TEXT,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY (plan_activity_id) REFERENCES plan_activities(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS progress_records (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      record_type TEXT NOT NULL,
      metric_name TEXT NOT NULL,
      metric_value REAL NOT NULL,
      metric_unit TEXT,
      source TEXT,
      record_date TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS exercise_catalogue (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      category TEXT NOT NULL,
      target_area TEXT NOT NULL,
      purpose TEXT,
      equipment TEXT,
      difficulty TEXT DEFAULT 'beginner',
      starting_position TEXT,
      instructions TEXT,
      sets INTEGER,
      reps TEXT,
      hold_duration TEXT,
      rest_period TEXT,
      breathing TEXT,
      common_mistakes TEXT,
      safety_precautions TEXT,
      easier_variation TEXT,
      image_url TEXT,
      video_url TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_movement_assessments_user ON movement_assessments(user_id, assessment_date);
    CREATE INDEX IF NOT EXISTS idx_activity_records_user_date ON activity_records(user_id, record_date);
    CREATE INDEX IF NOT EXISTS idx_meal_logs_user ON meal_logs(user_id, logged_at);
    CREATE INDEX IF NOT EXISTS idx_sleep_records_user ON sleep_records(user_id, record_date);
    CREATE INDEX IF NOT EXISTS idx_behaviour_records_user ON behaviour_records(user_id, record_date);
    CREATE INDEX IF NOT EXISTS idx_specialist_executions_workflow ON specialist_executions(workflow_id);
    CREATE INDEX IF NOT EXISTS idx_health_plans_user ON health_plans(user_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_plan_activities_plan ON plan_activities(plan_id);
    CREATE INDEX IF NOT EXISTS idx_progress_records_user ON progress_records(user_id, record_date);
  `);

  console.log('✅ Database initialized successfully');
}
