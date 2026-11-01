export function runPhysiotherapyAgent(userContext) {
  const { profile, health_screening, movement_assessments, history } = userContext;

  // Analyze movement assessments
  const shoulderAssessments = movement_assessments.filter(a => a.assessment_type === 'SHOULDER_RAISE');
  const balanceAssessments = movement_assessments.filter(a => a.assessment_type === 'ONE_LEG_STAND');

  const latestShoulder = shoulderAssessments[0];
  const latestBalance = balanceAssessments[0];
  const prevShoulder = shoulderAssessments[1];
  const prevBalance = balanceAssessments[1];

  // Safety gate check
  const unknownFields = [];
  if (health_screening?.heart_condition === 'UNKNOWN') unknownFields.push('heart condition');
  if (health_screening?.hypertension === 'UNKNOWN') unknownFields.push('hypertension status');
  if (health_screening?.joint_pain === 'UNKNOWN') unknownFields.push('joint pain');

  const hasHighRisk = health_screening?.heart_condition === 'YES' || health_screening?.hypertension === 'YES';
  const hasJointPain = health_screening?.joint_pain === 'YES';
  const safetyApproved = unknownFields.length === 0 && !hasHighRisk;

  // Shoulder analysis
  const shoulderFindings = [];
  let shoulderScore = 75;

  if (latestShoulder) {
    const leftRight = Math.abs((latestShoulder.left_measurement || 0) - (latestShoulder.right_measurement || 0));
    if (leftRight > 15) {
      shoulderFindings.push(`Notable asymmetry: ${leftRight.toFixed(0)}° difference between left and right shoulder`);
      shoulderScore -= 15;
    } else if (leftRight > 8) {
      shoulderFindings.push(`Mild asymmetry: ${leftRight.toFixed(0)}° difference between shoulders`);
      shoulderScore -= 8;
    } else {
      shoulderFindings.push('Good bilateral shoulder symmetry observed');
    }

    if (latestShoulder.left_measurement < 120 || latestShoulder.right_measurement < 120) {
      shoulderFindings.push('Shoulder elevation range is below functional reference threshold');
      shoulderScore -= 10;
    }

    if (prevShoulder) {
      const avgCurrent = ((latestShoulder.left_measurement || 0) + (latestShoulder.right_measurement || 0)) / 2;
      const avgPrev = ((prevShoulder.left_measurement || 0) + (prevShoulder.right_measurement || 0)) / 2;
      const change = avgCurrent - avgPrev;
      if (change > 5) shoulderFindings.push(`Improvement of ${change.toFixed(0)}° average range since last assessment`);
      else if (change < -5) shoulderFindings.push(`Decrease of ${Math.abs(change).toFixed(0)}° average range since last assessment`);
    }
  } else {
    shoulderFindings.push('No shoulder assessment data available — assessment recommended');
    shoulderScore = null;
  }

  // Balance analysis
  const balanceFindings = [];
  let balanceScore = 75;

  if (latestBalance) {
    const leftRight = Math.abs((latestBalance.left_measurement || 0) - (latestBalance.right_measurement || 0));
    if (leftRight > 8) {
      balanceFindings.push(`Balance asymmetry noted: ${leftRight.toFixed(0)}s difference between left and right stance`);
      balanceScore -= 15;
    } else {
      balanceFindings.push('Reasonable bilateral balance symmetry');
    }

    if (latestBalance.left_measurement < 10 || latestBalance.right_measurement < 10) {
      balanceFindings.push('Single-leg balance duration below functional reference threshold (10 seconds)');
      balanceScore -= 10;
    }

    if (prevBalance) {
      const avgCurrent = ((latestBalance.left_measurement || 0) + (latestBalance.right_measurement || 0)) / 2;
      const avgPrev = ((prevBalance.left_measurement || 0) + (prevBalance.right_measurement || 0)) / 2;
      const change = avgCurrent - avgPrev;
      if (change > 2) balanceFindings.push(`Balance duration improved by ${change.toFixed(1)}s since last assessment`);
    }
  } else {
    balanceFindings.push('No balance assessment data available — assessment recommended');
    balanceScore = null;
  }

  // Generate recommendations
  const recommendations = [];
  const activities = [];

  if (safetyApproved || unknownFields.length === 0) {
    if (latestShoulder) {
      recommendations.push({
        title: 'Shoulder Mobility Programme',
        description: 'Targeted wall slide exercises to maintain and improve shoulder range of motion',
        priority: 'HIGH',
        type: 'EXERCISE'
      });
      activities.push({
        exercise_id: 'ex-001',
        activity_title: 'Shoulder Wall Slide',
        description: 'Controlled shoulder mobility exercise targeting scapular movement',
        instructions: 'Stand facing a wall, slide arms upward within comfortable range. 3 sets × 10 reps.',
        time_block: 'MORNING',
        duration_minutes: 10,
        dosage: '3 sets × 10 reps, 60s rest',
        activity_type: 'EXERCISE',
        caution: hasJointPain ? 'Modified due to reported joint pain — stop if discomfort increases' : null
      });
    }

    if (latestBalance) {
      recommendations.push({
        title: 'Balance Training Protocol',
        description: 'Progressive single-leg balance practice to improve stability and proprioception',
        priority: 'HIGH',
        type: 'EXERCISE'
      });
      activities.push({
        exercise_id: 'ex-002',
        activity_title: 'Supported Single-Leg Balance',
        description: 'Progressive balance training with supported single-leg stance',
        instructions: 'Stand near support, balance on one leg for 10-20 seconds each side. 3 sets.',
        time_block: 'MORNING',
        duration_minutes: 8,
        dosage: '3 sets × 20s each side',
        activity_type: 'EXERCISE',
        caution: null
      });
    }

    recommendations.push({
      title: 'Functional Movement Maintenance',
      description: 'Sit-to-stand practice to maintain functional lower limb strength',
      priority: 'MEDIUM',
      type: 'EXERCISE'
    });
    activities.push({
      exercise_id: 'ex-003',
      activity_title: 'Sit-to-Stand Practice',
      description: 'Functional strength exercise for lower body and daily movement quality',
      instructions: 'From seated position, stand with control and return slowly. 3 sets × 10 reps.',
      time_block: 'AFTERNOON',
      duration_minutes: 8,
      dosage: '3 sets × 10 reps',
      activity_type: 'EXERCISE',
      caution: null
    });
  } else {
    recommendations.push({
      title: 'Complete Health Screening',
      description: `Please provide information on: ${unknownFields.join(', ')} to unlock personalized exercise prescription`,
      priority: 'HIGH',
      type: 'CLARIFICATION'
    });
    recommendations.push({
      title: 'General Movement Education',
      description: 'While awaiting safety clearance, review general movement guidance below',
      priority: 'MEDIUM',
      type: 'EDUCATION'
    });
    activities.push({
      exercise_id: 'ex-001',
      activity_title: 'Shoulder Wall Slide (Reference)',
      description: 'Reference exercise — consult physiotherapist before commencing',
      instructions: 'Reference only until safety screening is completed.',
      time_block: 'MORNING',
      duration_minutes: 10,
      dosage: 'To be prescribed after safety review',
      activity_type: 'REFERENCE',
      caution: 'Requires safety screening completion before personalized prescription'
    });
  }

  return {
    specialist: 'PHYSIOTHERAPY',
    status: 'COMPLETED',
    safety_approved: safetyApproved,
    unknown_fields: unknownFields,
    findings: {
      shoulder: { measurements: latestShoulder, findings: shoulderFindings, score: shoulderScore },
      balance: { measurements: latestBalance, findings: balanceFindings, score: balanceScore },
      previous_shoulder: prevShoulder,
      previous_balance: prevBalance
    },
    recommendations,
    activities,
    summary: safetyApproved
      ? `Movement assessment complete. ${shoulderFindings[0]}. ${balanceFindings[0]}.`
      : `Partial safety information — ${unknownFields.length} item(s) pending. Reference activities shown pending clearance.`,
    movewell_contribution: 'Movement quality, mobility and stability assessment with targeted exercise prescription'
  };
}
