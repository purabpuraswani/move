export function runStrengthConditioningAgent(userContext) {
  const { profile, health_screening, activity_records } = userContext;

  const exerciseFrequency = profile?.exercise_frequency || null;
  const exerciseMinutes = profile?.exercise_minutes || null;
  const exerciseTypes = profile?.exercise_types ? JSON.parse(profile.exercise_types) : [];
  const wellnessGoals = profile?.wellness_goals ? JSON.parse(profile.wellness_goals) : [];
  const activityPreferences = profile?.activity_preferences ? JSON.parse(profile.activity_preferences) : [];

  const hasBackPain = health_screening?.back_pain === 'YES';
  const hasJointPain = health_screening?.joint_pain === 'YES';
  const hasHeartCondition = health_screening?.heart_condition === 'YES';
  const hasHypertension = health_screening?.hypertension === 'YES';
  const hasHighRisk = hasHeartCondition || hasHypertension;

  const recentActivity = activity_records?.[0] || null;
  const weeklyExerciseMinutes = exerciseFrequency !== null && exerciseMinutes !== null
    ? exerciseFrequency * exerciseMinutes
    : null;

  const findings = [];
  const recommendations = [];
  const activities = [];

  // Exercise history analysis
  if (exerciseFrequency !== null) {
    if (exerciseFrequency >= 5) {
      findings.push(`High exercise frequency: ${exerciseFrequency} days per week`);
    } else if (exerciseFrequency >= 3) {
      findings.push(`Moderate exercise frequency: ${exerciseFrequency} days per week`);
    } else if (exerciseFrequency > 0) {
      findings.push(`Low exercise frequency: ${exerciseFrequency} day(s) per week — building consistency is key`);
    } else {
      findings.push('No regular exercise sessions reported');
    }
  }

  if (weeklyExerciseMinutes !== null) {
    if (weeklyExerciseMinutes >= 150) {
      findings.push(`Weekly exercise volume (${weeklyExerciseMinutes} min) meets WHO guidelines`);
    } else {
      findings.push(`Weekly exercise volume (${weeklyExerciseMinutes || 0} min) below WHO recommended 150 min`);
    }
  }

  if (exerciseTypes.length > 0) {
    findings.push(`Current exercise types: ${exerciseTypes.join(', ')}`);
  }

  const lackingStrengthTraining = !exerciseTypes.some(t =>
    ['strength', 'weights', 'resistance', 'gym', 'lifting'].some(kw => t.toLowerCase().includes(kw))
  );

  if (lackingStrengthTraining) {
    findings.push('No resistance or strength training reported — important addition for musculoskeletal health');
  }

  if (hasHighRisk) {
    findings.push('High-risk health condition noted — exercise prescription modified for safety');
  }
  if (hasBackPain) findings.push('Back pain reported — exercises selected to support spinal stability');
  if (hasJointPain) findings.push('Joint pain reported — low-impact options prioritised');

  // Recommendations
  if (lackingStrengthTraining && !hasHighRisk) {
    recommendations.push({
      title: 'Introduce Resistance Training',
      description: 'Add 2 sessions of body-weight or light resistance exercises per week to build functional strength',
      priority: 'HIGH',
      type: 'EXERCISE'
    });
  } else if (lackingStrengthTraining && hasHighRisk) {
    recommendations.push({
      title: 'Guided Strength Introduction',
      description: 'Consider supervised low-intensity resistance exercises once medical clearance is confirmed',
      priority: 'MEDIUM',
      type: 'REFERRAL'
    });
  }

  if (weeklyExerciseMinutes !== null && weeklyExerciseMinutes < 150) {
    recommendations.push({
      title: 'Build Weekly Exercise Volume',
      description: `Gradually increase from ${weeklyExerciseMinutes} min toward 150 min per week over 4-6 weeks`,
      priority: 'HIGH',
      type: 'ACTIVITY'
    });
  }

  recommendations.push({
    title: 'Progressive Exercise Overload',
    description: 'Increase exercise challenge gradually (5-10% per week) to continue making progress safely',
    priority: 'MEDIUM',
    type: 'EDUCATION'
  });

  // Glute bridge
  activities.push({
    exercise_id: 'ex-004',
    activity_title: 'Glute Bridge',
    description: 'Posterior chain strengthening to support spinal stability and lower body function',
    instructions: 'Lie on back, knees bent. Press heels and lift hips. Hold 2-3 seconds. Lower slowly. 3 sets × 12-15 reps.',
    time_block: 'AFTERNOON',
    duration_minutes: 10,
    dosage: '3 sets × 12-15 reps, 60s rest',
    activity_type: 'EXERCISE',
    caution: hasBackPain ? 'Perform with care due to reported back pain — stop if discomfort increases' : null
  });

  // Standing side leg raise
  activities.push({
    exercise_id: 'ex-005',
    activity_title: 'Standing Side Leg Raise',
    description: 'Hip abductor and core strengthening for lateral stability',
    instructions: 'Stand beside support. Raise outside leg slowly to side, hold briefly, lower. 3 sets × 10-12 each side.',
    time_block: 'AFTERNOON',
    duration_minutes: 10,
    dosage: '3 sets × 10-12 reps each side, 60s rest',
    activity_type: 'EXERCISE',
    caution: hasJointPain ? 'Monitor joint comfort — reduce range if needed' : null
  });

  activities.push({
    activity_title: 'Weekly Strength Log',
    description: 'Record your strength sessions to monitor progressive overload',
    instructions: 'After each strength session, note the exercises, sets, reps and how it felt. Review weekly to plan progression.',
    time_block: 'EVENING',
    duration_minutes: 5,
    dosage: 'After each session',
    activity_type: 'TRACKING',
    caution: null
  });

  // Strength score based on frequency and volume
  let strengthScore = null;
  if (exerciseFrequency !== null) {
    const freqScore = Math.min(100, (exerciseFrequency / 5) * 100);
    const volScore = weeklyExerciseMinutes !== null ? Math.min(100, (weeklyExerciseMinutes / 150) * 100) : 50;
    const typeBonus = lackingStrengthTraining ? 0 : 20;
    strengthScore = Math.round(Math.min(100, (freqScore * 0.4 + volScore * 0.4 + typeBonus * 0.2)));
  }

  return {
    specialist: 'STRENGTH_CONDITIONING',
    status: 'COMPLETED',
    findings,
    recommendations,
    activities,
    metrics: {
      exercise_frequency: exerciseFrequency,
      exercise_minutes: exerciseMinutes,
      weekly_exercise_minutes: weeklyExerciseMinutes,
      exercise_types: exerciseTypes,
      has_strength_training: !lackingStrengthTraining,
      strength_score: strengthScore
    },
    summary: exerciseFrequency !== null
      ? `Strength assessment: ${exerciseFrequency} sessions/week, ${weeklyExerciseMinutes || 0} min/week. ${lackingStrengthTraining ? 'Resistance training not yet included.' : 'Strength training included.'}`
      : 'Strength & conditioning assessment complete — exercise history recommended.',
    movewell_contribution: 'Strength training assessment, progressive overload guidance and functional fitness planning'
  };
}
