/**
 * The dashboard's movement snapshot, derived from stored assessment sessions.
 *
 * Everything here describes what was recorded. Nothing combines the three
 * checks into one number, compares a result to a population, or says whether
 * a result is good, bad, better or worse: this application has no validated
 * thresholds that would make any of that meaningful. A value that was not
 * recorded is never filled in.
 *
 * Pure functions only (no React, no fetch), so they are unit tested directly.
 */

export const SNAPSHOT_TESTS = [
  {
    id: "shoulder",
    title: "Hand / Shoulder Raise",
    shortTitle: "Shoulder",
    area: "Upper body movement",
    icon: "🖐",
  },
  {
    id: "ftsst",
    title: "Chair Sit-to-Stand ×5",
    shortTitle: "Sit-to-Stand",
    area: "Functional lower-body movement",
    icon: "🪑",
  },
  {
    id: "balance",
    title: "One-Leg Stand",
    shortTitle: "Balance",
    area: "Balance and stability",
    icon: "🦵",
  },
];

const STATUS_LABELS = {
  completed: "Completed",
  invalid: "Couldn't be measured",
  skipped: "Skipped",
  not_started: "Not completed",
};

const isNumber = (value) => typeof value === "number" && Number.isFinite(value);

function seconds(value) {
  return `${value.toFixed(1)} s`;
}

function holdSeconds(side) {
  if (!side?.attempted) return null;
  if (isNumber(side.holdDurationSeconds)) return side.holdDurationSeconds;
  if (isNumber(side.holdDurationMs)) return side.holdDurationMs / 1000;
  return null;
}

/**
 * The headline value and supporting details for one completed check, built
 * only from measurements that are present. `value` is null when a completed
 * check stored nothing this function knows how to show.
 */
export function describeMeasurements(testId, measurements) {
  const m = measurements || {};

  if (testId === "shoulder") {
    const leftReps = m.left?.repetitionCount;
    const rightReps = m.right?.repetitionCount;
    const leftDeg = m.left?.finalElevationDeg;
    const rightDeg = m.right?.finalElevationDeg;
    const details = [];

    let value = null;
    if (isNumber(leftReps) && isNumber(rightReps)) {
      value = `${leftReps + rightReps} raises recorded`;
      details.push(
        leftReps === rightReps
          ? `${leftReps} with each arm`
          : `${leftReps} left arm · ${rightReps} right arm`
      );
    }

    if (isNumber(leftDeg) && isNumber(rightDeg)) {
      details.push(`Final raise angle: ${Math.round(leftDeg)}° left · ${Math.round(rightDeg)}° right`);
    }

    if (isNumber(m.observableDifferenceDeg)) {
      details.push(`Difference between sides: ${Math.round(m.observableDifferenceDeg)}°`);
    }

    const compact = isNumber(leftDeg) && isNumber(rightDeg)
      ? `${Math.round(leftDeg)}° left · ${Math.round(rightDeg)}° right`
      : null;

    return { value, details, compact };
  }

  if (testId === "ftsst") {
    const time = m.completionTimeSeconds;
    const value = isNumber(time) ? `${time.toFixed(1)} seconds` : null;
    const details = [];

    if (isNumber(m.repetitionsDetected)) {
      details.push(`Time for ${m.repetitionsDetected} sit-to-stands`);
    }

    return { value, details, compact: value };
  }

  if (testId === "balance") {
    const left = holdSeconds(m.left);
    const right = holdSeconds(m.right);
    const parts = [];
    if (left !== null) parts.push(`${seconds(left)} left`);
    if (right !== null) parts.push(`${seconds(right)} right`);

    const value = parts.length ? parts.join(" · ") : null;
    const details = [];

    if (left !== null && right !== null) details.push("Time held on each leg");
    else if (left !== null) details.push("Time held on the left leg");
    else if (right !== null) details.push("Time held on the right leg");

    const limit = isNumber(m.maxDurationMs) ? Math.round(m.maxDurationMs / 1000) : null;
    const atLimit = [
      m.left?.attempted && m.left?.reachedMaxDuration ? "left" : null,
      m.right?.attempted && m.right?.reachedMaxDuration ? "right" : null,
    ].filter(Boolean);

    if (atLimit.length && limit) {
      details.push(`Held to the ${limit}-second limit on the ${atLimit.join(" and ")} leg`);
    }

    return { value, details, compact: value };
  }

  return { value: null, details: [], compact: null };
}

/** How many of the three checks are "completed" in a session. */
export function countCompleted(session) {
  if (!session?.tests) return 0;
  return SNAPSHOT_TESTS.filter((t) => session.tests[t.id]?.status === "completed").length;
}

/**
 * From a newest-first history listing ({ id, startedAt, statuses }), the most
 * recent earlier session in which each check was completed.
 * Returns { shoulder: listing|null, ftsst: ..., balance: ... }.
 */
export function previousCompletedSessions(listings, latestId) {
  const earlier = (listings || []).filter((entry) => entry && entry.id !== latestId);

  return Object.fromEntries(
    SNAPSHOT_TESTS.map(({ id }) => [
      id,
      earlier.find((entry) => entry.statuses?.[id] === "completed") || null,
    ])
  );
}

/**
 * The whole snapshot for the dashboard.
 *
 * `previousByTest` maps a test id to { startedAt, test } for that check's most
 * recent earlier completed result, or is omitted when there is none.
 */
export function buildMovementSnapshot(latest, previousByTest = {}) {
  if (!latest) {
    return {
      state: "none",
      completed: 0,
      remaining: SNAPSHOT_TESTS.length,
      total: SNAPSHOT_TESTS.length,
      badge: "NO CHECKS YET",
      lastUpdated: null,
      sessionId: null,
      tests: [],
    };
  }

  const tests = SNAPSHOT_TESTS.map((meta) => {
    const test = latest.tests?.[meta.id];
    const status = test?.status && STATUS_LABELS[test.status] ? test.status : "not_started";
    const completed = status === "completed";
    const described = completed ? describeMeasurements(meta.id, test.measurements) : null;

    const previous = previousByTest?.[meta.id];
    const previousDescribed =
      completed && previous?.test?.status === "completed"
        ? describeMeasurements(meta.id, previous.test.measurements)
        : null;

    return {
      ...meta,
      status,
      completed,
      statusLabel: STATUS_LABELS[status],
      value: described?.value ?? null,
      details: described?.details ?? [],
      note: status === "invalid" ? "We couldn't reliably assess this movement." : null,
      previous:
        previousDescribed?.compact
          ? { value: previousDescribed.compact, date: previous.startedAt ?? null }
          : null,
    };
  });

  const completed = tests.filter((t) => t.completed).length;
  const total = SNAPSHOT_TESTS.length;

  return {
    state: completed === total ? "complete" : "partial",
    completed,
    remaining: total - completed,
    total,
    badge: completed === 1 ? "1 CHECK COMPLETED" : `${completed} CHECKS COMPLETED`,
    lastUpdated: latest.completedAt || latest.startedAt || null,
    sessionId: latest.id ?? null,
    tests,
  };
}
