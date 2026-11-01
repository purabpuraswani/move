export function runBehaviourAgent(userContext) {
  const { profile, behaviour_records, activity_records } = userContext;

  const motivation = profile?.motivation || null;
  const barriers = profile?.barriers || null;
  const existingHabits = profile?.existing_habits || null;
  const sittingHours = profile?.sitting_hours || null;
  const movementBreaks = profile?.movement_breaks || null;

  // Analyze behaviour records
  const recentBehaviours = behaviour_records?.slice(0, 35) || [];
  const habitDays = new Set(recentBehaviours.map(b => b.record_date)).size;
  const completedHabits = recentBehaviours.filter(b => b.status === 'COMPLETED').length;
  const adherenceRate = recentBehaviours.length > 0
    ? Math.round((completedHabits / recentBehaviours.length) * 100)
    : null;

  const findings = [];
  const recommendations = [];
  const activities = [];

  // Sedentary analysis
  if (sittingHours !== null) {
    if (sittingHours > 8) {
      findings.push(`High sedentary time reported: ${sittingHours} hours sitting daily`);
    } else if (sittingHours > 6) {
      findings.push(`Moderate sedentary time: ${sittingHours} hours sitting daily — movement breaks important`);
    } else {
      findings.push(`Sitting time within reasonable range: ${sittingHours} hours daily`);
    }
  }

  if (movementBreaks !== null) {
    if (movementBreaks >= 6) {
      findings.push(`Good movement break frequency: ${movementBreaks} breaks per day`);
    } else if (movementBreaks >= 3) {
      findings.push(`Moderate movement breaks: ${movementBreaks} per day — aim for 6+`);
    } else {
      findings.push(`Infrequent movement breaks: ${movementBreaks} per day — increase to break sedentary patterns`);
    }
  }

  if (barriers) findings.push(`Reported barriers: ${barriers}`);
  if (existingHabits) findings.push(`Existing positive habits identified: ${existingHabits}`);

  if (habitDays > 0) {
    findings.push(`${habitDays} days of habit tracking recorded`);
    if (adherenceRate !== null) findings.push(`Habit completion rate: ${adherenceRate}%`);
  } else {
    findings.push('No habit tracking records yet — starting tracking will reveal patterns');
  }

  // Recommendations
  const needsBreaks = movementBreaks === null || movementBreaks < 6;
  const highSitting = sittingHours !== null && sittingHours > 6;

  if (needsBreaks || highSitting) {
    recommendations.push({
      title: 'Regular Movement Breaks',
      description: 'Set reminders to stand and move for 2-3 minutes every 45-60 minutes during seated work',
      priority: 'HIGH',
      type: 'BEHAVIOUR'
    });
  } else {
    recommendations.push({
      title: 'Maintain Movement Break Habit',
      description: 'Your movement break frequency is good. Continue the pattern and log consistency.',
      priority: 'MEDIUM',
      type: 'MAINTENANCE'
    });
  }

  if (motivation) {
    recommendations.push({
      title: 'Leverage Your Motivation',
      description: `Based on your motivation (${motivation}), focus on small daily wins that build toward this goal`,
      priority: 'MEDIUM',
      type: 'BEHAVIOUR'
    });
  }

  recommendations.push({
    title: 'Daily Habit Tracking',
    description: 'Track 3 key daily habits consistently — consistency data drives better recommendations',
    priority: 'MEDIUM',
    type: 'TRACKING'
  });

  // Activities
  if (needsBreaks) {
    activities.push({
      activity_title: 'Desk Break Reminder',
      description: 'Stand and walk for 2-3 minutes every hour during seated work',
      instructions: 'Set a timer or phone reminder every 45-60 minutes. When it goes off, stand up, walk to another room or do gentle stretches for 2-3 minutes before returning.',
      time_block: 'WORK_DAY',
      duration_minutes: 3,
      dosage: '6+ times per day, every 45-60 minutes',
      activity_type: 'BEHAVIOUR',
      caution: null
    });
  }

  activities.push({
    activity_title: 'Morning Intention Setting',
    description: 'Start each day with a 2-minute review of your wellness goals',
    instructions: 'Each morning, briefly review your 3 priority wellness goals. Choose one small action for the day that moves you toward each.',
    time_block: 'MORNING',
    duration_minutes: 2,
    dosage: 'Daily',
    activity_type: 'BEHAVIOUR',
    caution: null
  });

  activities.push({
    activity_title: 'Evening Habit Check-in',
    description: 'Record completed habits and note what helped or hindered you today',
    instructions: 'At the end of each day, mark your completed habits and write one brief note about the day.',
    time_block: 'EVENING',
    duration_minutes: 3,
    dosage: 'Daily',
    activity_type: 'TRACKING',
    caution: null
  });

  return {
    specialist: 'BEHAVIOUR',
    status: 'COMPLETED',
    findings,
    recommendations,
    activities,
    metrics: {
      sitting_hours: sittingHours,
      movement_breaks: movementBreaks,
      habit_days_tracked: habitDays,
      adherence_rate: adherenceRate
    },
    summary: sittingHours
      ? `Behaviour assessment complete. ${sittingHours}h sitting daily with ${movementBreaks || 0} movement breaks.`
      : 'Behaviour assessment complete — habit tracking started.',
    movewell_contribution: 'Sedentary behaviour analysis, habit building and daily routine optimisation'
  };
}
