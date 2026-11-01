import test from "node:test";
import assert from "node:assert/strict";
import { measuredResultsForAssessment, measurementValue } from "../assessmentDisplay.js";

test("renders both completed active assessments from one saved session", () => {
  const result = measuredResultsForAssessment({
    sessionId: "session-current",
    tests: {
      shoulder: { status: "completed", measurements: {
        left: { finalElevationDeg: 178.6 }, right: { finalElevationDeg: 173.6 },
      } },
      balance: { status: "completed", measurements: {
        left: { holdDurationSeconds: 30.01 }, right: { holdDurationSeconds: 30 },
      } },
    },
  }, { measured_results: { shoulder: { measurements: { left: 99 } } } });

  assert.equal(measurementValue("shoulder", result.shoulder.measurements.left), 178.6);
  assert.equal(measurementValue("shoulder", result.shoulder.measurements.right), 173.6);
  assert.equal(measurementValue("balance", result.balance.measurements.left), 30.01);
  assert.equal(measurementValue("balance", result.balance.measurements.right), 30);
  assert.equal(result.shoulder.unit, "degrees");
  assert.equal(result.balance.unit, "seconds");
});

test("does not use workflow measurements when a full session exists but lacks a measurement", () => {
  const result = measuredResultsForAssessment({
    sessionId: "session-current",
    tests: { shoulder: { status: "completed", measurements: null } },
  }, { measured_results: { balance: { measurements: { left: 30 } } } });

  assert.deepEqual(result, {});
});

test("workflow summary is a fallback only when the full assessment is unavailable", () => {
  const result = measuredResultsForAssessment(null, {
    measured_results: { balance: { measurements: { left: 14 }, unit: "seconds" } },
  });
  assert.equal(measurementValue("balance", result.balance.measurements.left), 14);
});
