import test from "node:test";
import assert from "node:assert/strict";

import {
  createExerciseAssessmentEngine,
  hasAssessmentEngine,
  ExerciseNotSupportedError,
} from "../index.js";
import { RepCountingEngine } from "../repCountingEngine.js";
import { HoldDurationEngine } from "../holdDurationEngine.js";
import { EXERCISE_ENGINE_CONFIG } from "../config.js";

// The exercises this application can actually assess with a camera. Was
// nine; supported-calf-raise was removed (see below) and the four Phase 6
// exercises that had been marked implemented in the library but had no
// engine were wired, so it is twelve.
const IMPLEMENTED_EXERCISE_IDS = [
  "chair-sit-to-stand",
  "wall-sit",
  "standing-knee-raise",
  "wall-push-up",
  "standing-side-leg-raise",
  "standing-hip-extension",
  "supported-single-leg-stand",
  "standing-shoulder-raise",
  "seated-marching",
  "standing-overhead-reach",
  "seated-knee-extension",
  "single-leg-reach-balance",
];

// Timed holds rather than counted repetitions.
const HOLD_DURATION_EXERCISE_IDS = [
  "wall-sit",
  "supported-single-leg-stand",
  "single-leg-reach-balance",
];

test("a configuration exists for every MoveNet-implemented exercise", () => {
  for (const id of IMPLEMENTED_EXERCISE_IDS) {
    assert.ok(hasAssessmentEngine(id), `expected an engine config for ${id}`);
  }
});

test("the list above is exactly what is configured, with nothing left over", () => {
  // The guard for the drift that made this file fail: the list was hand
  // maintained, so removing one configuration and adding four left it
  // describing a set that no longer existed. Comparing both directions
  // means a future change to config.js cannot silently disagree with the
  // expectations here -- it either updates this list or fails.
  assert.deepEqual(
    [...IMPLEMENTED_EXERCISE_IDS].sort(),
    Object.keys(EXERCISE_ENGINE_CONFIG).sort(),
  );
});

test("exercises the camera cannot measure have no engine configuration", () => {
  // heel-to-toe-stand was always absent. supported-calf-raise was removed:
  // its assessment is a heel raise, and MoveNet estimates 17 body points of
  // which none is the heel or the toe, so the movement is not observable at
  // all. A configuration would have offered an assessment that could only
  // ever have produced an invented number.
  for (const id of ["heel-to-toe-stand", "supported-calf-raise"]) {
    assert.equal(hasAssessmentEngine(id), false, id);
    assert.throws(
      () => createExerciseAssessmentEngine(id),
      ExerciseNotSupportedError,
      id,
    );
  }
});

test("an unknown exercise id throws ExerciseNotSupportedError, not a crash", () => {
  assert.throws(
    () => createExerciseAssessmentEngine("not-a-real-exercise"),
    ExerciseNotSupportedError
  );
});

test("hold-duration exercises produce a HoldDurationEngine", () => {
  for (const id of HOLD_DURATION_EXERCISE_IDS) {
    assert.ok(createExerciseAssessmentEngine(id) instanceof HoldDurationEngine, id);
  }
});

test("rep-counting exercises produce a RepCountingEngine", () => {
  for (const id of IMPLEMENTED_EXERCISE_IDS) {
    if (HOLD_DURATION_EXERCISE_IDS.includes(id)) continue;

    assert.ok(createExerciseAssessmentEngine(id) instanceof RepCountingEngine, id);
  }
});

test("every configured exercise's engine is independently usable end to end", () => {
  for (const id of Object.keys(EXERCISE_ENGINE_CONFIG)) {
    const engine = createExerciseAssessmentEngine(id);
    assert.doesNotThrow(() => engine.push(0, 0));
    assert.doesNotThrow(() => engine.summary());
  }
});

test("exercises given the same configuration are independent instances", () => {
  const first = createExerciseAssessmentEngine("wall-sit");
  const second = createExerciseAssessmentEngine("wall-sit");

  // wall-sit's configured smoothingWindow is 5: the median filter reports
  // null (and the engine treats that as "invalid") until it has that many
  // samples, so enough pushes are needed to fill it before a duration
  // starts accumulating at all.
  // wall-sit's configured valid range is 80-110 (a knee-flexion angle in
  // degrees), not a 0-1 ratio — use a value inside that range.
  for (let i = 0; i < 5; i += 1) {
    first.push(95, i * 1000);
  }
  first.push(95, 6000);

  assert.notEqual(first.summary().durationSeconds, second.summary().durationSeconds);
  assert.equal(second.summary().durationSeconds, 0);
});
