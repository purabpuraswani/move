export function runRecoveryAgent(userContext) {
  const { profile, sleep_records } = userContext;

  const profileSleep = profile?.sleep_hours || null;
  const profileSleepQuality = profile?.sleep_quality || null;
  const profileStress = profile?.stress_level || null;

  // Use recent sleep records if available
  const recentSleep = sleep_records?.slice(0, 7) || [];
  const avgDuration = recentSleep.length > 0
    ? recentSleep.reduce((sum, r) => sum + r.sleep_duration, 0) / recentSleep.length
    : profileSleep;

  const qualityMap = { 'POOR': 1, 'FAIR': 2, 'GOOD': 3, 'EXCELLENT': 4 };
  const recentQualities = recentSleep.map(r => qualityMap[r.sleep_quality] || 0).filter(q => q > 0);
  const avgQuality = recentQualities.length > 0
    ? recentQualities.reduce((sum, q) => sum + q, 0) / recentQualities.length
    : (qualityMap[profileSleepQuality] || null);

  const avgStress = recentSleep.length > 0
    ? recentSleep.reduce((sum, r) => sum + (r.stress_level || 5), 0) / recentSleep.length
    : profileStress;

  const findings = [];
  const recommendations = [];
  const activities = [];

  // Sleep duration analysis
  if (avgDuration !== null) {
    if (avgDuration >= 7 && avgDuration <= 9) {
      findings.push(`Sleep duration within healthy range: ${avgDuration.toFixed(1)} hours average`);
    } else if (avgDuration < 7) {
      findings.push(`Sleep duration below recommended range: ${avgDuration.toFixed(1)} hours (target: 7-9 hours)`);
    } else {
      findings.push(`Sleep duration above typical range: ${avgDuration.toFixed(1)} hours — monitor for quality`);
    }
  } else {
    findings.push('Sleep duration not yet recorded — please log sleep data');
  }

  // Sleep quality
  if (avgQuality !== null) {
    const qualityLabels = ['', 'Poor', 'Fair', 'Good', 'Excellent'];
    const qualityLabel = qualityLabels[Math.round(avgQuality)] || 'Unknown';
    findings.push(`Sleep quality: ${qualityLabel} (based on ${recentSleep.length > 0 ? 'logged records' : 'profile report'})`);
  } else {
    findings.push('Sleep quality not yet reported — this is important for recovery assessment');
  }

  // Stress analysis
  if (avgStress !== null) {
    if (avgStress <= 3) {
      findings.push(`Stress level reported as low: ${avgStress.toFixed(0)}/10`);
    } else if (avgStress <= 6) {
      findings.push(`Moderate stress level: ${avgStress.toFixed(0)}/10 — recovery strategies recommended`);
    } else {
      findings.push(`Elevated stress: ${avgStress.toFixed(0)}/10 — prioritise recovery and stress management`);
    }
  }

  // Recommendations
  if (avgDuration !== null && avgDuration < 7) {
    recommendations.push({
      title: 'Improve Sleep Duration',
      description: 'Aim for 7-9 hours of sleep. Set a consistent bedtime 30 minutes earlier this week.',
      priority: 'HIGH',
      type: 'RECOVERY'
    });
  } else if (avgDuration !== null) {
    recommendations.push({
      title: 'Maintain Sleep Consistency',
      description: 'Your sleep duration is good. Focus on maintaining a consistent sleep schedule.',
      priority: 'MEDIUM',
      type: 'MAINTENANCE'
    });
  }

  if (avgStress !== null && avgStress > 5) {
    recommendations.push({
      title: 'Stress Management',
      description: 'Incorporate evening relaxation practices to lower pre-sleep stress',
      priority: 'HIGH',
      type: 'RECOVERY'
    });
  }

  recommendations.push({
    title: 'Evening Wind-Down Routine',
    description: 'Establish a 20-30 minute pre-sleep routine to support quality sleep',
    priority: 'MEDIUM',
    type: 'RECOVERY'
  });

  // Activities
  activities.push({
    activity_title: 'Evening Wind-Down',
    description: 'Follow a consistent 20-minute pre-sleep routine',
    instructions: 'Begin 30 minutes before bed: dim lights, avoid screens, do gentle breathing or stretching. Ensure room is cool and quiet.',
    time_block: 'EVENING',
    duration_minutes: 20,
    dosage: 'Nightly',
    activity_type: 'RECOVERY',
    caution: null
  });

  activities.push({
    activity_title: "Log Today's Sleep & Recovery",
    description: 'Record sleep duration, quality and stress level each morning',
    instructions: 'Each morning, log: hours slept, sleep quality (Poor/Fair/Good/Excellent), and stress level (1-10). This builds your recovery profile.',
    time_block: 'MORNING',
    duration_minutes: 2,
    dosage: 'Daily',
    activity_type: 'TRACKING',
    caution: null
  });

  if (avgStress !== null && avgStress > 4) {
    activities.push({
      activity_title: 'Deep Breathing Practice',
      description: '5-minute diaphragmatic breathing for relaxation and stress reduction',
      instructions: 'Sit or lie comfortably. Breathe in slowly for 4 counts, hold for 4 counts, breathe out for 6 counts. Repeat for 5 minutes.',
      time_block: 'EVENING',
      duration_minutes: 5,
      dosage: 'Daily',
      activity_type: 'RECOVERY',
      caution: null
    });
  }

  const sleepScore = avgDuration !== null
    ? Math.min(100, Math.round(avgDuration >= 7 ? 80 + (avgDuration - 7) * 10 : (avgDuration / 7) * 80))
    : null;

  return {
    specialist: 'WELLNESS_RECOVERY',
    status: 'COMPLETED',
    findings,
    recommendations,
    activities,
    metrics: {
      avg_sleep_duration: avgDuration,
      avg_sleep_quality: avgQuality,
      avg_stress_level: avgStress,
      sleep_records_count: recentSleep.length,
      sleep_score: sleepScore
    },
    summary: avgDuration
      ? `Recovery assessment: ${avgDuration.toFixed(1)}h average sleep. ${findings[1] || ''}`
      : 'Recovery assessment complete — sleep logging recommended.',
    movewell_contribution: 'Sleep quality analysis, stress monitoring and recovery optimisation'
  };
}
