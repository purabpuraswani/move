/**
 * Per-exercise engine configuration: which of the two generic engines
 * (RepCountingEngine, HoldDurationEngine) applies to each Exercise Library
 * entry that MoveNet actually supports today, and the thresholds it runs
 * with.
 *
 * Every threshold below is a SYSTEM DECISION, not a clinical or validated
 * value — the same discipline as backend/need_assessment/rules.py and
 * src/assessment/config/protocol.js. They are placeholders chosen to make
 * the engines runnable and testable; before any of these exercises is
 * scored against a live camera feed, these numbers need the same kind of
 * scrutiny protocol.js's already-shipped thresholds have had, and ideally a
 * physio/healthcare review pass, exactly as docs/architecture.md's Phase 1
 * "known limitations" section already flagged for the Need Assessment
 * thresholds.
 *
 * `heel-to-toe-stand` is deliberately absent: its movenet_support.implemented
 * is false in backend/exercise_library/data.py, and this file does not
 * invent a configuration for an exercise the library itself says is not
 * yet measurable.
 *
 * What is NOT here: how to turn camera keypoints into the raw angle each
 * config expects as its engine's input signal. That per-exercise
 * "keypoints -> one number" extraction (what shoulderLogic.js does for the
 * shoulder-raise test) is separate work, out of Phase 2's declared scope
 * (a movement-assessment FOUNDATION, not a live wiring of all ten
 * exercises to the camera) — see docs/architecture.md for the honest
 * status of each exercise.
 */

export const ENGINE_TYPES = Object.freeze({
  REP_COUNTING: "rep-counting",
  HOLD_DURATION: "hold-duration",
});

export const EXERCISE_ENGINE_CONFIG = {
  "chair-sit-to-stand": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    signal: "kneeExtensionAngleDeg",
    enterThreshold: 155,
    exitThreshold: 120,
    minDurationMs: 500,
    maxDurationMs: 15000,
    smoothingWindow: 5,
    targetRepetitions: 10,
  },
  "wall-sit": {
    engineType: ENGINE_TYPES.HOLD_DURATION,
    signal: "kneeFlexionAngleDeg",
    validMin: 80,
    validMax: 110,
    stabilizationMs: 400,
    maxDurationMs: 60000,
    smoothingWindow: 5,
  },
  "standing-knee-raise": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    signal: "hipFlexionAngleDeg",
    enterThreshold: 60,
    exitThreshold: 20,
    minDurationMs: 400,
    maxDurationMs: 8000,
    smoothingWindow: 5,
    targetRepetitions: 10,
  },
  "wall-push-up": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    signal: "elbowFlexionAngleDeg",
    enterThreshold: 35,
    exitThreshold: 10,
    minDurationMs: 400,
    maxDurationMs: 8000,
    smoothingWindow: 5,
    targetRepetitions: 10,
  },
  "standing-side-leg-raise": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    signal: "hipAbductionAngleDeg",
    enterThreshold: 20,
    exitThreshold: 5,
    minDurationMs: 400,
    maxDurationMs: 8000,
    smoothingWindow: 5,
    targetRepetitions: 10,
  },
  "standing-hip-extension": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    signal: "hipExtensionAngleDeg",
    enterThreshold: 15,
    exitThreshold: 5,
    minDurationMs: 400,
    maxDurationMs: 8000,
    smoothingWindow: 5,
    targetRepetitions: 10,
  },
  "supported-single-leg-stand": {
    engineType: ENGINE_TYPES.HOLD_DURATION,
    signal: "liftedFootHeightRatio",
    validMin: 0.1,
    validMax: 1,
    stabilizationMs: 400,
    maxDurationMs: 30000,
    smoothingWindow: 3,
  },
  "standing-shoulder-raise": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    signal: "armElevationAngleDeg",
    enterThreshold: 55,
    exitThreshold: 30,
    minDurationMs: 400,
    maxDurationMs: 12000,
    smoothingWindow: 5,
    targetRepetitions: 10,
  },

  // --- Phase 6 batch, wired in the final integration pass ------------------
  //
  // These four were marked movenet_support.implemented in the exercise
  // library but had no engine configuration, so nothing could run them: the
  // library claimed an assessment the application could not perform. Each
  // one reuses a signal extractor that already exists and is unit-tested in
  // signals.js, so no new measurement was invented to close the gap -- only
  // the configuration that was missing.
  //
  // standing-hamstring-stretch is deliberately NOT here. A hamstring stretch
  // is judged by where the stretch is felt, and the trunk-hinge angle a
  // camera can see does not distinguish a good one from a rounded back. It
  // is corrected in the library rather than given a threshold that would
  // score the wrong thing.
  //
  // The thresholds below are SYSTEM DECISIONS on exactly the same footing as
  // every other number in this file: chosen to be runnable and plausible,
  // not clinically validated, and still awaiting the physio review this
  // module's header already flags.

  "seated-marching": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    // Seated, so the thigh starts horizontal and lifts from there; the same
    // hip-flexion signal as the standing knee raise, with a lower threshold
    // because the available range from a seated start is smaller.
    signal: "hipFlexionAngleDeg",
    enterThreshold: 100,
    exitThreshold: 85,
    minDurationMs: 300,
    maxDurationMs: 6000,
    smoothingWindow: 5,
    targetRepetitions: 20,
  },

  "standing-overhead-reach": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    // Arm elevation from hanging down, the same observable the baseline
    // shoulder test uses. Overhead is near 180; the enter threshold sits
    // below that so a full reach is not required to count.
    signal: "armElevationAngleDeg",
    enterThreshold: 150,
    exitThreshold: 60,
    minDurationMs: 400,
    maxDurationMs: 8000,
    smoothingWindow: 5,
    targetRepetitions: 10,
  },

  "seated-knee-extension": {
    engineType: ENGINE_TYPES.REP_COUNTING,
    // Interior knee angle, as in the sit-to-stand: ~90 seated, straightening
    // toward 180 as the leg extends.
    signal: "kneeExtensionAngleDeg",
    enterThreshold: 160,
    exitThreshold: 110,
    minDurationMs: 400,
    maxDurationMs: 8000,
    smoothingWindow: 5,
    targetRepetitions: 10,
  },

  "single-leg-reach-balance": {
    engineType: ENGINE_TYPES.HOLD_DURATION,
    // A balance hold, so duration rather than repetitions -- the same
    // torso-normalised foot-height ratio the supported single-leg stand
    // uses, with the same open-ended upper bound.
    signal: "liftedFootHeightRatio",
    validMin: 0.08,
    validMax: 1.5,
    stabilizationMs: 500,
    maxDurationMs: 60000,
    smoothingWindow: 5,
  },

};
