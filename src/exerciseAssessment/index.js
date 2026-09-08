/**
 * Factory: build the right generic engine for a given exercise.
 *
 * This is the one place that connects an Exercise Library id
 * (backend/exercise_library/data.py's exercise_id, mirrored in
 * config.js) to a configured RepCountingEngine or HoldDurationEngine —
 * so a future camera-integration phase has one function to call, not a
 * per-exercise if/else scattered across the UI.
 */

import { EXERCISE_ENGINE_CONFIG, ENGINE_TYPES } from "./config.js";
import { HoldDurationEngine } from "./holdDurationEngine.js";
import { RepCountingEngine } from "./repCountingEngine.js";

export class ExerciseNotSupportedError extends Error {}

/**
 * @param {string} exerciseId one of backend/exercise_library/data.py's exercise_id values
 * @returns {RepCountingEngine|HoldDurationEngine}
 * @throws {ExerciseNotSupportedError} if the exercise has no engine configuration
 *   (currently: heel-to-toe-stand, whose movenet_support.implemented is false)
 */
export function createExerciseAssessmentEngine(exerciseId) {
  const config = EXERCISE_ENGINE_CONFIG[exerciseId];

  if (!config) {
    throw new ExerciseNotSupportedError(
      `no movement-assessment configuration exists for exercise "${exerciseId}" ` +
        "(it may not yet have an implemented MoveNet-based assessment)"
    );
  }

  if (config.engineType === ENGINE_TYPES.REP_COUNTING) {
    return new RepCountingEngine({
      enterThreshold: config.enterThreshold,
      exitThreshold: config.exitThreshold,
      smoothingWindow: config.smoothingWindow,
      minDurationMs: config.minDurationMs,
      maxDurationMs: config.maxDurationMs,
      targetRepetitions: config.targetRepetitions,
    });
  }

  if (config.engineType === ENGINE_TYPES.HOLD_DURATION) {
    return new HoldDurationEngine({
      validMin: config.validMin,
      validMax: config.validMax,
      smoothingWindow: config.smoothingWindow,
      stabilizationMs: config.stabilizationMs,
      maxDurationMs: config.maxDurationMs,
    });
  }

  // Unreachable while ENGINE_TYPES is closed and config.js only uses its
  // values, but fails loudly rather than silently if that ever changes.
  throw new ExerciseNotSupportedError(
    `exercise "${exerciseId}" has an unrecognised engineType "${config.engineType}"`
  );
}

/** True if createExerciseAssessmentEngine(exerciseId) would succeed. */
export function hasAssessmentEngine(exerciseId) {
  return exerciseId in EXERCISE_ENGINE_CONFIG;
}

export { ENGINE_TYPES };
export { HOLD_STATE } from "./holdDurationEngine.js";
