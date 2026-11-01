export function runNutritionAgent(userContext) {
  const { profile, meal_logs } = userContext;

  const waterIntake = profile?.water_intake_liters || null;
  const fruitVegServings = profile?.fruit_veg_servings || null;
  const foodPreferences = profile?.food_preferences || '';
  const nutritionGoals = profile?.nutrition_goals || '';
  const restrictions = profile?.food_restrictions || '';

  // Analyze recent meal logs
  const recentMeals = meal_logs?.slice(0, 21) || [];
  const mealTypes = recentMeals.map(m => m.meal_type);
  const hasBreakfast = mealTypes.some(t => t === 'BREAKFAST');
  const mealLogDays = new Set(recentMeals.map(m => m.logged_at?.substring(0, 10))).size;

  const findings = [];
  const recommendations = [];
  const activities = [];

  // Water analysis
  if (waterIntake !== null) {
    if (waterIntake >= 2.0) {
      findings.push(`Good hydration reported: ${waterIntake}L daily`);
    } else if (waterIntake >= 1.5) {
      findings.push(`Hydration slightly below optimal: ${waterIntake}L daily (target: 2.0L)`);
    } else {
      findings.push(`Hydration needs improvement: ${waterIntake}L daily (target: 2.0L minimum)`);
    }
  } else {
    findings.push('Daily water intake not recorded — tracking recommended');
  }

  // Fruit and veg
  if (fruitVegServings !== null) {
    if (fruitVegServings >= 5) {
      findings.push(`Good fruit and vegetable intake: ${fruitVegServings} servings daily`);
    } else {
      findings.push(`Fruit and vegetable intake below target: ${fruitVegServings}/5 servings daily`);
    }
  }

  // Meal pattern
  if (mealLogDays > 0) {
    findings.push(`${mealLogDays} days of meal logging recorded recently`);
    if (!hasBreakfast) findings.push('Breakfast not consistently logged — consider regular breakfast timing');
  } else {
    findings.push('No recent meal logs — meal tracking will help personalise nutrition guidance');
  }

  // Recommendations
  if (waterIntake === null || waterIntake < 2.0) {
    recommendations.push({
      title: 'Hydration Target',
      description: 'Aim for 2.0L of water daily. Use a measured bottle to track intake.',
      priority: 'HIGH',
      type: 'NUTRITION'
    });
  } else {
    recommendations.push({
      title: 'Maintain Hydration Consistency',
      description: `You're meeting your hydration target of ${waterIntake}L. Continue monitoring daily.`,
      priority: 'MEDIUM',
      type: 'MAINTENANCE'
    });
  }

  recommendations.push({
    title: 'Balanced Meal Pattern',
    description: 'Include protein, complex carbohydrates and vegetables at each main meal',
    priority: 'MEDIUM',
    type: 'NUTRITION'
  });

  if (mealLogDays < 3) {
    recommendations.push({
      title: 'Start Meal Logging',
      description: 'Track your meals for at least 3 days to receive personalised nutrition insights',
      priority: 'MEDIUM',
      type: 'TRACKING'
    });
  }

  // Activities
  activities.push({
    activity_title: 'Morning Hydration',
    description: 'Start the day with a glass of water before breakfast',
    instructions: 'Drink 300-400ml of water within 30 minutes of waking. Continue throughout the day toward 2.0L total.',
    time_block: 'MORNING',
    duration_minutes: 2,
    dosage: '300-400ml on waking, 2.0L total daily',
    activity_type: 'NUTRITION',
    caution: null
  });

  activities.push({
    activity_title: 'Balanced Breakfast',
    description: 'Start the day with a nutritious balanced breakfast',
    instructions: restrictions
      ? `Include protein and complex carbs. Note your preferences: ${restrictions}`
      : 'Include a protein source (eggs, yogurt, legumes), complex carbohydrates and fruit or vegetables.',
    time_block: 'MORNING',
    duration_minutes: 15,
    dosage: 'Once daily',
    activity_type: 'NUTRITION',
    caution: restrictions ? `Dietary notes: ${restrictions}` : null
  });

  activities.push({
    activity_title: "Log Today's Meals",
    description: 'Record all meals and snacks using the meal tracking feature',
    instructions: 'After each meal, record the food description, portion and meal type in the nutrition section.',
    time_block: 'EVENING',
    duration_minutes: 5,
    dosage: 'After each meal',
    activity_type: 'TRACKING',
    caution: null
  });

  const hydrationScore = waterIntake !== null
    ? Math.min(100, Math.round((waterIntake / 2.0) * 100))
    : null;

  return {
    specialist: 'NUTRITION',
    status: 'COMPLETED',
    findings,
    recommendations,
    activities,
    metrics: {
      water_intake: waterIntake,
      fruit_veg_servings: fruitVegServings,
      meal_log_days: mealLogDays,
      hydration_score: hydrationScore
    },
    summary: findings[0] || 'Nutrition assessment complete — meal logging recommended for personalised guidance',
    movewell_contribution: 'Nutrition pattern analysis, hydration tracking and meal guidance'
  };
}
