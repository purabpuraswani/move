export function runActivityAgent(userContext) {
  const { profile, activity_records } = userContext;

  // Use most recent activity record or profile defaults
  const latestActivity = activity_records?.[0] || null;

  const dailySteps = latestActivity?.daily_steps || profile?.daily_steps || null;
  const sittingHours = latestActivity?.sitting_hours || profile?.sitting_hours || null;
  const movementBreaks = latestActivity?.movement_breaks || profile?.movement_breaks || null;
  const exerciseFrequency = profile?.exercise_frequency || null;
  const exerciseMinutes = profile?.exercise_minutes || null;
  const weeklyExerciseMinutes = exerciseFrequency !== null && exerciseMinutes !== null
    ? exerciseFrequency * exerciseMinutes
    : null;

  // Score components (all 0-100 scale)
  const stepsScore = dailySteps !== null ? Math.min(100, (dailySteps / 10000) * 100) : null;
  const frequencyScore = exerciseFrequency !== null ? Math.min(100, (exerciseFrequency / 7) * 100) : null;
  const durationScore = weeklyExerciseMinutes !== null ? Math.min(100, (weeklyExerciseMinutes / 300) * 100) : null;
  const sittingScore = sittingHours !== null ? Math.max(0, 100 - Math.max(0, sittingHours - 4) * 20) : null;
  const breaksScore = movementBreaks !== null ? Math.min(100, (movementBreaks / 6) * 100) : null;

  // Calculate overall score only from available components
  const components = [
    { score: stepsScore, weight: 0.30, label: 'Daily Steps' },
    { score: frequencyScore, weight: 0.20, label: 'Exercise Frequency' },
    { score: durationScore, weight: 0.20, label: 'Exercise Duration' },
    { score: sittingScore, weight: 0.20, label: 'Sitting Duration' },
    { score: breaksScore, weight: 0.10, label: 'Movement Breaks' }
  ];

  const available = components.filter(c => c.score !== null);
  let activityScore = null;

  if (available.length > 0) {
    const totalWeight = available.reduce((sum, c) => sum + c.weight, 0);
    const weightedSum = available.reduce((sum, c) => sum + (c.score * c.weight), 0);
    activityScore = Math.round(weightedSum / totalWeight);
  }

  const findings = [];
  const recommendations = [];
  const activities = [];

  // Step analysis
  if (dailySteps !== null) {
    if (dailySteps >= 10000) findings.push(`Excellent step count: ${dailySteps.toLocaleString()} steps daily`);
    else if (dailySteps >= 7500) findings.push(`Good step count: ${dailySteps.toLocaleString()} steps — approaching 10,000 target`);
    else if (dailySteps >= 5000) findings.push(`Moderate activity: ${dailySteps.toLocaleString()} steps — increase walking opportunities`);
    else findings.push(`Low step count: ${dailySteps.toLocaleString()} steps — significant walking increase recommended`);
  } else {
    findings.push('Daily steps not recorded — connect a wearable or log manually');
  }

  // Sitting check
  if (sittingHours !== null && sittingHours > 7) {
    findings.push(`High daily sitting time: ${sittingHours}h — even with exercise, prolonged sitting is an independent risk factor`);
  } else if (sittingHours !== null) {
    findings.push(`Daily sitting: ${sittingHours}h`);
  }

  // Exercise analysis
  if (exerciseFrequency !== null && exerciseMinutes !== null) {
    findings.push(`Exercise: ${exerciseFrequency} days/week × ${exerciseMinutes} min = ${weeklyExerciseMinutes} min/week`);
    if (weeklyExerciseMinutes >= 150) findings.push('Weekly exercise volume meets recommended guidelines (150+ min)');
    else findings.push(`Weekly exercise volume below guidelines: ${weeklyExerciseMinutes}/150 min minimum`);
  }

  // Recommendations
  if (dailySteps !== null && dailySteps < 8000) {
    recommendations.push({
      title: 'Increase Daily Steps',
      description: `Current: ${dailySteps.toLocaleString()} steps. Add short 10-min walks to approach 8,000+ steps.`,
      priority: 'HIGH',
      type: 'ACTIVITY'
    });
  }

  if (sittingHours !== null && sittingHours > 7) {
    recommendations.push({
      title: 'Reduce Prolonged Sitting',
      description: 'Break up sitting with 5-minute standing or walking breaks every hour',
      priority: 'HIGH',
      type: 'BEHAVIOUR'
    });
  }

  recommendations.push({
    title: 'Weekly Activity Structure',
    description: exerciseFrequency !== null && exerciseFrequency >= 5
      ? 'Maintain current exercise frequency — consider adding variety'
      : 'Build toward 5 active days per week with a mix of cardiovascular and strength activity',
    priority: 'MEDIUM',
    type: 'ACTIVITY'
  });

  // Activities
  const stepTarget = dailySteps ? Math.min(dailySteps + 2000, 10000) : 8000;

  activities.push({
    activity_title: 'Morning Walk',
    description: `Start the day with a ${dailySteps && dailySteps < 5000 ? '15' : '20'}-minute brisk walk`,
    instructions: `Walk at a comfortable pace that allows conversation. Aim for ${Math.round(stepTarget * 0.3).toLocaleString()} steps on this walk. Track using phone or wearable if available.`,
    time_block: 'MORNING',
    duration_minutes: dailySteps && dailySteps < 5000 ? 15 : 20,
    dosage: `Daily — target ${stepTarget.toLocaleString()} total steps today`,
    activity_type: 'CARDIO',
    caution: null
  });

  if (sittingHours !== null && sittingHours > 7) {
    activities.push({
      activity_title: 'Lunchtime Walk',
      description: '10-minute walk to break up prolonged sitting during the work day',
      instructions: 'During your lunch break, take a 10-minute walk outside or around the building. This breaks sedentary time and adds to daily step count.',
      time_block: 'AFTERNOON',
      duration_minutes: 10,
      dosage: 'Daily, at lunch',
      activity_type: 'CARDIO',
      caution: null
    });
  }

  activities.push({
    activity_title: 'Log Daily Activity',
    description: 'Record steps, sitting time and any exercise completed today',
    instructions: 'At the end of the day, log your step count, hours sitting and any exercise completed. Use the Activity section in the app.',
    time_block: 'EVENING',
    duration_minutes: 2,
    dosage: 'Daily',
    activity_type: 'TRACKING',
    caution: null
  });

  return {
    specialist: 'ACTIVITY',
    status: 'COMPLETED',
    findings,
    recommendations,
    activities,
    metrics: {
      daily_steps: dailySteps,
      sitting_hours: sittingHours,
      movement_breaks: movementBreaks,
      exercise_frequency: exerciseFrequency,
      exercise_minutes: exerciseMinutes,
      weekly_exercise_minutes: weeklyExerciseMinutes,
      activity_score: activityScore,
      score_components: components.map(c => ({ label: c.label, score: c.score, weight: c.weight }))
    },
    summary: dailySteps
      ? `Activity assessment: ${dailySteps.toLocaleString()} daily steps, ${sittingHours || '?'}h sitting. Activity score: ${activityScore || 'N/A'}/100.`
      : 'Activity assessment complete — step tracking recommended.',
    movewell_contribution: 'Daily activity monitoring, step tracking and sedentary behaviour reduction'
  };
}
