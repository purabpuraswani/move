import bcrypt from 'bcryptjs';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from './connection.js';
import { initializeDatabase } from './initialize.js';

const exercises = [
  {
    id: 'ex-001',
    name: 'Shoulder Wall Slide',
    category: 'Mobility',
    target_area: 'Shoulders & Upper Back',
    purpose: 'Support comfortable shoulder movement and upper-body mobility through controlled scapular movement',
    equipment: 'Wall',
    difficulty: 'beginner',
    starting_position: 'Stand facing a wall, feet shoulder-width apart, forearms resting against the wall at shoulder height',
    instructions: JSON.stringify([
      'Stand approximately 30cm from a wall',
      'Place both forearms flat against the wall, elbows at shoulder height',
      'Slowly slide your arms upward along the wall as far as comfortable',
      'Keep contact with the wall throughout the movement',
      'Hold at the top for 2-3 seconds',
      'Slowly slide arms back to starting position',
      'Repeat 10 times'
    ]),
    sets: 3,
    reps: '10',
    hold_duration: '2-3 seconds at top',
    rest_period: '60 seconds between sets',
    breathing: 'Exhale as you slide up, inhale as you return',
    common_mistakes: JSON.stringify(['Arching the lower back', 'Shrugging the shoulders', 'Moving too quickly', 'Forcing beyond comfortable range']),
    safety_precautions: JSON.stringify(['Stop if you feel sharp pain', 'Work within your comfortable range only', 'Consult your physiotherapist if pain persists']),
    easier_variation: 'Perform with just one arm at a time, or reduce the slide height',
    image_url: '/exercises/images/shoulder-wall-slide.jpg',
    video_url: null
  },
  {
    id: 'ex-002',
    name: 'Supported Single-Leg Balance',
    category: 'Balance & Stability',
    target_area: 'Legs, Ankles & Core',
    purpose: 'Practice controlled single-leg balance to improve stability and proprioception',
    equipment: 'Chair or wall for support',
    difficulty: 'beginner',
    starting_position: 'Stand beside a stable chair or wall, one hand lightly resting on it for support',
    instructions: JSON.stringify([
      'Stand beside a stable chair or counter',
      'Place one hand lightly on the support',
      'Shift your weight gradually onto one leg',
      'Lift the opposite foot just slightly off the ground',
      'Keep your standing knee soft, not locked',
      'Maintain an upright, comfortable posture',
      'Hold for 10-20 seconds',
      'Lower the foot and switch sides',
      'Repeat 3 times each side'
    ]),
    sets: 3,
    reps: '3 each side',
    hold_duration: '10-20 seconds',
    rest_period: '30 seconds between sets',
    breathing: 'Breathe naturally and steadily throughout',
    common_mistakes: JSON.stringify(['Gripping the support tightly', 'Locking the standing knee', 'Leaning to one side', 'Holding the breath']),
    safety_precautions: JSON.stringify(['Always have support nearby', 'Stop if you feel dizzy', 'Perform near a wall for safety']),
    easier_variation: 'Keep more weight through the supporting hand, or only lift toes rather than full foot',
    image_url: '/exercises/images/single-leg-balance.jpg',
    video_url: null
  },
  {
    id: 'ex-003',
    name: 'Sit-to-Stand',
    category: 'Functional Strength',
    target_area: 'Quadriceps, Glutes & Core',
    purpose: 'Practice controlled standing and sitting movements to build functional lower-body strength',
    equipment: 'Stable chair',
    difficulty: 'beginner',
    starting_position: 'Sit on a firm, stable chair with feet flat on the floor, hip-width apart',
    instructions: JSON.stringify([
      'Sit on a firm chair with feet flat on the floor',
      'Sit near the front edge of the seat',
      'Place feet hip-width apart, knees above ankles',
      'Lean slightly forward from the hips',
      'Push through your feet and stand up with control',
      'Straighten fully at the top',
      'Slowly lower back to seated position',
      'Control the movement throughout, especially sitting down',
      'Repeat 10-12 times'
    ]),
    sets: 3,
    reps: '10-12',
    hold_duration: null,
    rest_period: '60-90 seconds between sets',
    breathing: 'Exhale as you stand up, inhale as you sit down',
    common_mistakes: JSON.stringify(['Using arm momentum', 'Dropping down into the seat', 'Knees caving inward', 'Leaning too far forward']),
    safety_precautions: JSON.stringify(['Use armrests for assistance if needed initially', 'Choose a chair height that allows comfortable sitting', 'Stop if you feel knee pain']),
    easier_variation: 'Use a higher chair or use both armrests for support when standing',
    image_url: '/exercises/images/sit-to-stand.jpg',
    video_url: null
  },
  {
    id: 'ex-004',
    name: 'Glute Bridge',
    category: 'Strength',
    target_area: 'Glutes, Hamstrings & Lower Back',
    purpose: 'Practice controlled hip extension to strengthen the posterior chain and support spinal stability',
    equipment: 'Exercise mat (optional)',
    difficulty: 'beginner',
    starting_position: 'Lie on your back with knees bent, feet flat on the floor hip-width apart, arms by your sides',
    instructions: JSON.stringify([
      'Lie on your back with knees bent and feet flat on the floor',
      'Position feet hip-width apart, close enough that you can touch your heels',
      'Arms rest comfortably by your sides',
      'Tighten your gluteal muscles gently',
      'Press through your heels and lift your hips toward the ceiling',
      'Lift until your body forms a straight line from shoulders to knees',
      'Hold at the top for 2-3 seconds',
      'Slowly lower your hips back to the starting position',
      'Repeat 12-15 times'
    ]),
    sets: 3,
    reps: '12-15',
    hold_duration: '2-3 seconds at top',
    rest_period: '60 seconds between sets',
    breathing: 'Exhale as you lift the hips, inhale as you lower',
    common_mistakes: JSON.stringify(['Overextending the lower back', 'Pushing with the lower back instead of glutes', 'Feet too far from hips', 'Dropping hips quickly']),
    safety_precautions: JSON.stringify(['Stop if you feel lower back discomfort', 'Keep the movement controlled', 'Do not perform if you have active back pain without physiotherapy guidance']),
    easier_variation: 'Reduce the height of the bridge or keep one foot on the floor for support',
    image_url: '/exercises/images/glute-bridge.jpg',
    video_url: null
  },
  {
    id: 'ex-005',
    name: 'Standing Side Leg Raise',
    category: 'Strength & Balance',
    target_area: 'Hip Abductors & Core',
    purpose: 'Practice controlled hip abduction to improve lateral hip strength and single-leg stability',
    equipment: 'Chair or wall for support',
    difficulty: 'beginner',
    starting_position: 'Stand beside a stable support, feet together, torso upright',
    instructions: JSON.stringify([
      'Stand beside a chair or wall for light support',
      'Place feet together, stand tall with good posture',
      'Keep the supporting leg slightly soft at the knee',
      'Slowly raise the outside leg to the side, keeping toes pointed forward',
      'Lift to a comfortable height — do not lean your torso',
      'Hold briefly at the top',
      'Slowly lower the leg back to starting position',
      'Complete all reps on one side, then switch',
      'Repeat 10-12 times each side'
    ]),
    sets: 3,
    reps: '10-12 each side',
    hold_duration: '1-2 seconds at top',
    rest_period: '60 seconds between sets',
    breathing: 'Exhale as you raise the leg, inhale as you lower',
    common_mistakes: JSON.stringify(['Leaning the torso to the opposite side', 'Rotating the lifted leg', 'Using momentum instead of control', 'Lifting too high']),
    safety_precautions: JSON.stringify(['Keep the movement within comfortable range', 'Stop if you feel hip or groin discomfort', 'Use support as needed']),
    easier_variation: 'Reduce the height of the raise or perform seated with ankle weights removed',
    image_url: '/exercises/images/standing-side-leg-raise.jpg',
    video_url: null
  }
];

function dateOffset(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().substring(0, 10);
}

async function seed() {
  initializeDatabase();
  const db = getDb();

  // Check if demo user already exists
  const existing = db.prepare('SELECT id FROM users WHERE email = ?').get('demo@movewell.ai');
  if (existing) {
    console.log('ℹ️  Demo user already exists — skipping seed');
    process.exit(0);
  }

  const userId = uuidv4();
  const profileId = uuidv4();
  const screeningId = uuidv4();

  const passwordHash = await bcrypt.hash('Demo1234!', 10);

  // 1. Create demo user
  db.prepare(`
    INSERT INTO users (id, name, email, password_hash)
    VALUES (?, ?, ?, ?)
  `).run(userId, 'Alex Chen', 'demo@movewell.ai', passwordHash);

  // 2. Create user profile
  db.prepare(`
    INSERT INTO user_profiles (
      id, user_id, date_of_birth, height, weight, work_pattern,
      wellness_goals, activity_preferences, food_preferences, food_restrictions,
      allergies, water_intake_liters, fruit_veg_servings, sleep_hours, sleep_quality,
      stress_level, motivation, barriers, existing_habits, preferred_changes,
      nutrition_goals, daily_steps, exercise_frequency, exercise_minutes,
      sitting_hours, movement_breaks, exercise_types, onboarding_completed
    ) VALUES (
      ?, ?, ?, ?, ?, ?,
      ?, ?, ?, ?,
      ?, ?, ?, ?, ?,
      ?, ?, ?, ?, ?,
      ?, ?, ?, ?,
      ?, ?, ?, ?
    )
  `).run(
    profileId, userId, '1988-04-15', 175.0, 78.0, 'OFFICE',
    JSON.stringify(['Improve fitness', 'Reduce stress', 'Better sleep']),
    JSON.stringify(['Walking', 'Cycling', 'Yoga']),
    'Enjoys Asian cuisine, occasional vegetarian meals',
    'Trying to reduce processed foods',
    'None', 1.8, 4, 6.5, 'FAIR',
    6, 'Feel more energetic and reduce back pain from desk work',
    'Long working hours, fatigue after work', 'Morning coffee walk, weekend cycling',
    'Move more during work hours, improve sleep routine',
    'Eat more whole foods and vegetables',
    7200, 3, 40,
    9.0, 2, JSON.stringify(['Walking', 'Cycling']), 1
  );

  // 3. Health screening
  db.prepare(`
    INSERT INTO health_screenings (id, user_id, diabetes, hypertension, heart_condition,
      injury_history, joint_pain, back_pain, neck_pain, other_conditions)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    screeningId, userId,
    'NO', 'NO', 'UNKNOWN',
    'YES', 'YES', 'YES', 'NO',
    'Previous right knee injury (2019), resolved'
  );

  // 4. Movement assessments (2 historical: shoulder + balance each)
  const assessments = [
    { id: uuidv4(), type: 'SHOULDER_RAISE', left: 145, right: 130, unit: 'degrees', date: dateOffset(14) },
    { id: uuidv4(), type: 'ONE_LEG_STAND', left: 12, right: 8, unit: 'seconds', date: dateOffset(14) },
    { id: uuidv4(), type: 'SHOULDER_RAISE', left: 150, right: 138, unit: 'degrees', date: dateOffset(7) },
    { id: uuidv4(), type: 'ONE_LEG_STAND', left: 15, right: 11, unit: 'seconds', date: dateOffset(7) },
  ];

  const insertAssessment = db.prepare(`
    INSERT INTO movement_assessments (id, user_id, assessment_type, left_measurement, right_measurement, unit, assessment_date, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'COMPLETED')
  `);
  for (const a of assessments) {
    insertAssessment.run(a.id, userId, a.type, a.left, a.right, a.unit, a.date);
  }

  // 5. Activity records for last 7 days
  const activityData = [
    { steps: 7800, sit: 9.0, breaks: 2, freq: 0, mins: 0, type: 'NONE' },
    { steps: 6500, sit: 9.5, breaks: 1, freq: 0, mins: 0, type: 'NONE' },
    { steps: 9200, sit: 7.0, breaks: 4, freq: 1, mins: 45, type: 'Cycling' },
    { steps: 5400, sit: 10.0, breaks: 1, freq: 0, mins: 0, type: 'NONE' },
    { steps: 8100, sit: 8.5, breaks: 3, freq: 0, mins: 0, type: 'NONE' },
    { steps: 11200, sit: 5.0, breaks: 6, freq: 1, mins: 60, type: 'Cycling' },
    { steps: 7200, sit: 9.0, breaks: 2, freq: 0, mins: 0, type: 'NONE' },
  ];

  const insertActivity = db.prepare(`
    INSERT INTO activity_records (id, user_id, record_date, daily_steps, sitting_hours,
      movement_breaks, exercise_frequency, exercise_minutes, exercise_type, source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')
  `);

  for (let i = 0; i < 7; i++) {
    const d = activityData[i];
    insertActivity.run(uuidv4(), userId, dateOffset(6 - i), d.steps, d.sit, d.breaks, d.freq, d.mins, d.type);
  }

  // 6. Meal logs for last 3 days
  const meals = [];
  for (let day = 2; day >= 0; day--) {
    const date = dateOffset(day);
    meals.push(
      { type: 'BREAKFAST', food: 'Oats with banana and honey', portion: '1 bowl', cal: 320, date },
      { type: 'LUNCH', food: 'Brown rice with stir-fried tofu and vegetables', portion: '1 plate', cal: 480, date },
      { type: 'DINNER', food: 'Grilled chicken with steamed broccoli and quinoa', portion: '1 plate', cal: 520, date },
      { type: 'SNACK', food: 'Apple and handful of almonds', portion: 'Small', cal: 180, date }
    );
  }

  const insertMeal = db.prepare(`
    INSERT INTO meal_logs (id, user_id, meal_type, food_description, portion, calories_optional, logged_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  for (const m of meals) {
    insertMeal.run(uuidv4(), userId, m.type, m.food, m.portion, m.cal, `${m.date}T12:00:00`);
  }

  // 7. Sleep records for last 7 days
  const sleepData = [
    { dur: 6.5, quality: 'FAIR', stress: 6 },
    { dur: 7.0, quality: 'GOOD', stress: 5 },
    { dur: 5.5, quality: 'POOR', stress: 8 },
    { dur: 7.5, quality: 'GOOD', stress: 4 },
    { dur: 6.0, quality: 'FAIR', stress: 7 },
    { dur: 8.0, quality: 'EXCELLENT', stress: 3 },
    { dur: 6.5, quality: 'FAIR', stress: 6 },
  ];

  const insertSleep = db.prepare(`
    INSERT INTO sleep_records (id, user_id, sleep_duration, sleep_quality, stress_level, recovery_notes, record_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  for (let i = 0; i < 7; i++) {
    const s = sleepData[i];
    insertSleep.run(
      uuidv4(), userId, s.dur, s.quality, s.stress,
      s.quality === 'POOR' ? 'Woke up several times' : null,
      dateOffset(6 - i)
    );
  }

  // 8. Behaviour records for last 7 days
  const habits = [
    { key: 'morning_walk', name: 'Morning Walk' },
    { key: 'water_intake', name: 'Drink 2L Water' },
    { key: 'movement_breaks', name: 'Hourly Movement Break' },
  ];

  const statusPattern = ['COMPLETED', 'COMPLETED', 'SKIPPED', 'COMPLETED', 'MISSED', 'COMPLETED', 'COMPLETED'];

  const insertBehaviour = db.prepare(`
    INSERT INTO behaviour_records (id, user_id, habit_key, habit_name, status, notes, record_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);

  for (let day = 6; day >= 0; day--) {
    const date = dateOffset(day);
    for (const habit of habits) {
      const status = statusPattern[6 - day];
      insertBehaviour.run(
        uuidv4(), userId, habit.key, habit.name, status,
        status === 'SKIPPED' ? 'Busy day at work' : null,
        date
      );
    }
  }

  // 9. Exercise catalogue
  const insertExercise = db.prepare(`
    INSERT OR IGNORE INTO exercise_catalogue (
      id, name, category, target_area, purpose, equipment, difficulty,
      starting_position, instructions, sets, reps, hold_duration, rest_period,
      breathing, common_mistakes, safety_precautions, easier_variation, image_url, video_url
    ) VALUES (
      ?, ?, ?, ?, ?, ?, ?,
      ?, ?, ?, ?, ?, ?,
      ?, ?, ?, ?, ?, ?
    )
  `);

  for (const ex of exercises) {
    insertExercise.run(
      ex.id, ex.name, ex.category, ex.target_area, ex.purpose, ex.equipment, ex.difficulty,
      ex.starting_position, ex.instructions, ex.sets, ex.reps, ex.hold_duration, ex.rest_period,
      ex.breathing, ex.common_mistakes, ex.safety_precautions, ex.easier_variation, ex.image_url, ex.video_url
    );
  }

  // Also execute initial workflow to populate the initial Unified Health Plan
  const { runWorkflow } = await import('../orchestrator/workflowOrchestrator.js');
  await runWorkflow(userId);

  console.log('✅ Seed complete — demo user created and initial workflow executed: demo@movewell.ai / Demo1234!');
  process.exit(0);
}

seed().catch(err => {
  console.error('❌ Seed failed:', err);
  process.exit(1);
});
