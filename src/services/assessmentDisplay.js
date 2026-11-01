const ACTIVE_TESTS = ["shoulder", "balance"];

/** Return measurements from one saved session without combining sessions. */
export function measuredResultsForAssessment(assessment, workflowSummary = null) {
  const tests = assessment?.tests;
  if (tests && typeof tests === "object") {
    return Object.fromEntries(ACTIVE_TESTS.flatMap((testId) => {
      const entry = tests[testId];
      if (entry?.status !== "completed" || !entry.measurements || typeof entry.measurements !== "object") return [];
      return [[testId, { measurements: entry.measurements, unit: testId === "shoulder" ? "degrees" : "seconds" }]];
    }));
  }

  // Workflow snapshots are useful when a page was reached immediately after
  // saving and the full assessment response is not available. The caller
  // passes only the summary associated with that same workflow result.
  const saved = workflowSummary?.measured_results;
  if (!saved || typeof saved !== "object") return {};
  return Object.fromEntries(ACTIVE_TESTS
    .filter((testId) => saved[testId]?.measurements && typeof saved[testId].measurements === "object")
    .map((testId) => [testId, saved[testId]]));
}

export function measurementValue(testId, value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (!value || typeof value !== "object") return null;
  const candidates = testId === "shoulder"
    ? [value.finalElevationDeg, value.peakElevationDeg, value.elevationDeg]
    : [value.holdDurationSeconds, value.durationSeconds, value.holdSeconds];
  return candidates.find((candidate) => typeof candidate === "number" && Number.isFinite(candidate)) ?? null;
}
