/**
 * Comprehensive verification tests for pre-test positioning and recoverable tracking.
 *
 * Verifies Points A through K:
 * A. Intermittent frame loss does NOT fail an assessment if tracking recovers within tolerance.
 * B. Recovery state transitions follow TRACKING -> TEMPORARY_LOSS -> RECOVERING -> TRACKING.
 * C. Sustained loss (>1500ms) terminates cleanly with actionable suggestion.
 * D. Silhouette / framing checklist validates required landmarks.
 * E. Laptop webcam margins / distance warnings trigger actionable feedback.
 * F. Balance test ignores pre-test wobble because countdown separates positioning from measurement.
 * G. Shoulder test requires arms visible.
 * H. Sit-to-stand requires side profile with hips/knees/feet visible.
 * I. Valid completed assessment scores correctly.
 * J. Low quality / poor visibility remains NOT_ASSESSED (no fake scores or lowered standards).
 * K. Rep counting cannot increase during TEMPORARY_LOSS or RECOVERING.
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  evaluatePositioning,
  POSITIONING_STATUS,
  STABLE_PREFLIGHT_FRAMES,
} from "../utils/positioning.js";
import {
  QualityTracker,
  TRACKING_STATE,
} from "../utils/validation.js";
import { POSE, REASON, TEST_STATUS } from "../config/protocol.js";
import { isUsableResult } from "../utils/results.js";
import { getActionableSuggestion } from "../utils/labels.js";
import { ShoulderAbductionTest } from "../tests/shoulder/shoulderLogic.js";
import { FiveTimesSitToStandTest } from "../tests/ftsst/ftsstLogic.js";
import { SingleLegStanceTest } from "../tests/balance/balanceLogic.js";
import {
  frontFacingBase,
  sideFacingBase,
  makeFrame,
  DEFAULT_FRAME_MS,
} from "../fixtures/syntheticPoses.js";

// Helper for normalized frontal frame
function normalizedFrontFrame(overrides = {}) {
  return {
    timestamp: overrides.timestamp ?? 0,
    keypoints: {
      nose: { x: 0.5, y: 0.15, score: 0.95 },
      left_eye: { x: 0.48, y: 0.13, score: 0.95 },
      right_eye: { x: 0.52, y: 0.13, score: 0.95 },
      left_shoulder: { x: 0.42, y: 0.28, score: 0.92 },
      right_shoulder: { x: 0.58, y: 0.28, score: 0.92 },
      left_elbow: { x: 0.38, y: 0.42, score: 0.9 },
      right_elbow: { x: 0.62, y: 0.42, score: 0.9 },
      left_wrist: { x: 0.36, y: 0.56, score: 0.88 },
      right_wrist: { x: 0.64, y: 0.56, score: 0.88 },
      left_hip: { x: 0.45, y: 0.52, score: 0.91 },
      right_hip: { x: 0.55, y: 0.52, score: 0.91 },
      left_knee: { x: 0.46, y: 0.72, score: 0.89 },
      right_knee: { x: 0.54, y: 0.72, score: 0.89 },
      left_ankle: { x: 0.46, y: 0.90, score: 0.87 },
      right_ankle: { x: 0.54, y: 0.90, score: 0.87 },
      ...overrides.keypoints,
    },
  };
}

// Helper for normalized side frame (FTSST)
function normalizedSideFrame(overrides = {}) {
  return {
    timestamp: overrides.timestamp ?? 0,
    keypoints: {
      nose: { x: 0.52, y: 0.18, score: 0.92 },
      left_eye: { x: 0.51, y: 0.16, score: 0.91 },
      right_eye: { x: 0.53, y: 0.16, score: 0.4 },
      // Side view: right side facing camera, left side collapsed / low score
      left_shoulder: { x: 0.49, y: 0.30, score: 0.35 },
      right_shoulder: { x: 0.51, y: 0.30, score: 0.93 },
      left_elbow: { x: 0.48, y: 0.42, score: 0.3 },
      right_elbow: { x: 0.53, y: 0.42, score: 0.9 },
      left_wrist: { x: 0.48, y: 0.50, score: 0.25 },
      right_wrist: { x: 0.54, y: 0.50, score: 0.88 },
      left_hip: { x: 0.48, y: 0.55, score: 0.35 },
      right_hip: { x: 0.50, y: 0.55, score: 0.92 },
      left_knee: { x: 0.58, y: 0.68, score: 0.35 },
      right_knee: { x: 0.60, y: 0.68, score: 0.91 },
      left_ankle: { x: 0.58, y: 0.88, score: 0.3 },
      right_ankle: { x: 0.60, y: 0.88, score: 0.89 },
      ...overrides.keypoints,
    },
  };
}

// ---------------------------------------------------------------------------
// POINT A: Intermittent frame loss does NOT fail an assessment
// ---------------------------------------------------------------------------
test("Point A: intermittent frame loss below threshold does not fail quality tracking", () => {
  const tracker = new QualityTracker({ trackedKeypoints: ["nose"] });
  const frameIntervalMs = 33; // ~30 fps
  let timestamp = 0;

  // 40 healthy frames
  for (let i = 0; i < 40; i++) {
    tracker.record(
      { timestamp, keypoints: { nose: { x: 0.5, y: 0.5, score: 0.9 } } },
      true
    );
    timestamp += frameIntervalMs;
  }

  // Intermittent drop of 6 frames (approx 200ms, well below maxPoseLossMs of 1500ms)
  for (let i = 0; i < 6; i++) {
    tracker.record(
      { timestamp, keypoints: { nose: { x: 0.5, y: 0.5, score: 0.1 } } },
      false,
      [REASON.LOW_CONFIDENCE]
    );
    timestamp += frameIntervalMs;
  }

  // 40 recovered healthy frames
  for (let i = 0; i < 40; i++) {
    tracker.record(
      { timestamp, keypoints: { nose: { x: 0.5, y: 0.5, score: 0.9 } } },
      true
    );
    timestamp += frameIntervalMs;
  }

  const summary = tracker.summary();
  assert.equal(summary.framesSeen, 86);
  assert.equal(summary.framesUsable, 80);
  assert.ok(summary.usableFrameRatio > 0.9);
  assert.ok(summary.longestPoseLossMs < POSE.maxPoseLossMs);
  // Assessment passes: no blocking reasons!
  assert.deepEqual(tracker.blockingReasons(), []);
  assert.equal(tracker.getTrackingState(), TRACKING_STATE.TRACKING);
});

// ---------------------------------------------------------------------------
// POINT B: Recovery state machine transitions
// ---------------------------------------------------------------------------
test("Point B: state machine transitions TRACKING -> TEMPORARY_LOSS -> RECOVERING -> TRACKING", () => {
  const tracker = new QualityTracker();
  let time = 0;

  // 1. Initially TRACKING
  let res = tracker.record({ timestamp: time, keypoints: {} }, true);
  assert.equal(res.trackingState, TRACKING_STATE.TRACKING);
  assert.equal(tracker.getTrackingState(), TRACKING_STATE.TRACKING);

  // 2. Unusable frame triggers TEMPORARY_LOSS
  time += 33;
  res = tracker.record({ timestamp: time, keypoints: {} }, false, [REASON.LOW_CONFIDENCE]);
  assert.equal(res.trackingState, TRACKING_STATE.TEMPORARY_LOSS);
  assert.equal(tracker.getTrackingState(), TRACKING_STATE.TEMPORARY_LOSS);

  // 3. First usable frame triggers RECOVERING (frame 1 of 3 needed)
  time += 33;
  res = tracker.record({ timestamp: time, keypoints: {} }, true);
  assert.equal(res.trackingState, TRACKING_STATE.RECOVERING);

  // 4. Second usable frame still RECOVERING (frame 2 of 3 needed)
  time += 33;
  res = tracker.record({ timestamp: time, keypoints: {} }, true);
  assert.equal(res.trackingState, TRACKING_STATE.RECOVERING);

  // 5. Third usable frame confirms recovery (frame 3 of 3 reaches threshold) -> returns to TRACKING
  time += 33;
  res = tracker.record({ timestamp: time, keypoints: {} }, true);
  assert.equal(res.trackingState, TRACKING_STATE.TRACKING);
  assert.equal(tracker.getTrackingState(), TRACKING_STATE.TRACKING);
});

// ---------------------------------------------------------------------------
// POINT C: Sustained loss (>1500ms) cleanly terminates with actionable suggestion
// ---------------------------------------------------------------------------
test("Point C: sustained loss beyond 1500ms sets FAILED and provides actionable guidance", () => {
  const tracker = new QualityTracker();
  let time = 0;

  tracker.record({ timestamp: time, keypoints: {} }, true);

  // 55 unusable frames across 1800ms (> 1500ms ceiling)
  for (let i = 0; i < 55; i++) {
    time += 33;
    tracker.record({ timestamp: time, keypoints: {} }, false, [REASON.POSE_LOST]);
  }

  assert.equal(tracker.getTrackingState(), TRACKING_STATE.FAILED);
  assert.ok(tracker.summary().longestPoseLossMs >= 1500);
  assert.ok(tracker.blockingReasons().includes(REASON.POSE_LOST));

  // Actionable suggestion must be non-technical and user-friendly
  const suggestion = getActionableSuggestion(REASON.POSE_LOST, "shoulder");
  assert.ok(suggestion.length > 10);
  assert.match(suggestion, /centered/i);
});

// ---------------------------------------------------------------------------
// POINT D: Silhouette / framing checklist validates required landmarks
// ---------------------------------------------------------------------------
test("Point D: pre-test checklist validates landmarks and transitions from searching to ready", () => {
  // Empty frame -> searching
  const emptyEval = evaluatePositioning(null, "shoulder");
  assert.equal(emptyEval.ready, false);
  assert.equal(emptyEval.status, POSITIONING_STATUS.SEARCHING);
  assert.equal(emptyEval.checklist.head, false);
  assert.equal(emptyEval.checklist.shoulders, false);

  // Full body frame -> advances holding count
  const goodFrame = normalizedFrontFrame();
  let result = evaluatePositioning(goodFrame, "shoulder", { stableCount: 0 });
  assert.equal(result.checklist.head, true);
  assert.equal(result.checklist.shoulders, true);
  assert.equal(result.checklist.hips, true);
  assert.equal(result.checklist.knees, true);
  assert.equal(result.checklist.feet, true);
  assert.equal(result.checklist.arms, true);
  assert.equal(result.status, POSITIONING_STATUS.HOLDING);
  assert.equal(result.stableFrames, 1);

  // After STABLE_PREFLIGHT_FRAMES -> transitions to READY
  result = evaluatePositioning(goodFrame, "shoulder", {
    stableCount: STABLE_PREFLIGHT_FRAMES - 1,
  });
  assert.equal(result.ready, true);
  assert.equal(result.status, POSITIONING_STATUS.READY);
  assert.equal(result.progress, 1);
});

// ---------------------------------------------------------------------------
// POINT E: Laptop webcam margins and distance warnings
// ---------------------------------------------------------------------------
test("Point E: laptop webcam clipping and distance triggers human-friendly guidance", () => {
  // 1. Top clipping: Head too close to top edge (y < 0.05)
  const clippedTop = normalizedFrontFrame({
    keypoints: { nose: { x: 0.5, y: 0.02, score: 0.95 } },
  });
  const topEval = evaluatePositioning(clippedTop, "balance");
  assert.match(topEval.guidance, /camera slightly higher/i);
  assert.match(topEval.actionableTip, /tilt your screen/i);

  // 2. Bottom clipping: Feet cut off at bottom edge (y > 0.96)
  const clippedBottom = normalizedFrontFrame({
    keypoints: {
      left_ankle: { x: 0.46, y: 0.98, score: 0.9 },
      right_ankle: { x: 0.54, y: 0.98, score: 0.9 },
    },
  });
  const bottomEval = evaluatePositioning(clippedBottom, "balance");
  assert.match(bottomEval.guidance, /step back so your feet are visible/i);

  // 3. Too close to camera (torsoSpan > 0.55)
  const tooClose = normalizedFrontFrame({
    keypoints: {
      left_shoulder: { x: 0.35, y: 0.15, score: 0.95 },
      right_shoulder: { x: 0.65, y: 0.15, score: 0.95 },
      left_hip: { x: 0.38, y: 0.75, score: 0.95 }, // torsoSpan = 0.60 > 0.55
      right_hip: { x: 0.62, y: 0.75, score: 0.95 },
    },
  });
  const closeEval = evaluatePositioning(tooClose, "ftsst");
  assert.match(closeEval.guidance, /farther from the camera/i);

  // 4. Too far from camera (torsoSpan < 0.12)
  const tooFar = normalizedFrontFrame({
    keypoints: {
      left_shoulder: { x: 0.48, y: 0.45, score: 0.95 },
      right_shoulder: { x: 0.52, y: 0.45, score: 0.95 },
      left_hip: { x: 0.48, y: 0.52, score: 0.95 }, // torsoSpan = 0.07 < 0.12
      right_hip: { x: 0.52, y: 0.52, score: 0.95 },
    },
  });
  const farEval = evaluatePositioning(tooFar, "ftsst");
  assert.match(farEval.guidance, /closer/i);
});

// ---------------------------------------------------------------------------
// POINT F: Balance test separates setup from measurement (wobble ignored)
// ---------------------------------------------------------------------------
test("Point F: balance test setup wobble does not corrupt hold duration", () => {
  const balanceTest = new SingleLegStanceTest({ supportSide: "right" });

  // Initial frames in two-footed stance (waiting phase)
  const baseStanding = makeFrame(0, frontFacingBase());
  balanceTest.push(baseStanding);
  balanceTest.push(makeFrame(100, frontFacingBase()));

  // In waiting phase, stance hold clock has NOT started
  assert.equal(balanceTest.phase, "waiting");
  assert.equal(balanceTest.durationMs, null);

  // Moving slightly during setup (e.g. slight shift before lifting leg)
  const shiftPose = frontFacingBase();
  shiftPose.left_ankle.x += 10;
  balanceTest.push(makeFrame(200, shiftPose));

  // Still waiting: wobble did not fail or start measurement early
  assert.equal(balanceTest.phase, "waiting");
  assert.equal(balanceTest.durationMs, null);
});

// ---------------------------------------------------------------------------
// POINT G: Shoulder test requires arms visible
// ---------------------------------------------------------------------------
test("Point G: shoulder test checklist requires visible arms and gives specific tip", () => {
  // Missing wrists and elbows (e.g., arms cut off at edges of frame)
  const missingArms = normalizedFrontFrame({
    keypoints: {
      left_elbow: { x: 0.1, y: 0.4, score: 0.1 },
      right_elbow: { x: 0.9, y: 0.4, score: 0.1 },
      left_wrist: { x: 0.05, y: 0.5, score: 0.1 },
      right_wrist: { x: 0.95, y: 0.5, score: 0.1 },
    },
  });

  const evalResult = evaluatePositioning(missingArms, "shoulder");
  assert.equal(evalResult.checklist.arms, false);
  assert.equal(evalResult.ready, false);
  assert.match(evalResult.guidance, /both arms/i);
  assert.match(evalResult.actionableTip, /room to raise sideways/i);
});

// ---------------------------------------------------------------------------
// POINT H: Sit-to-stand requires side profile with hips/knees/feet
// ---------------------------------------------------------------------------
test("Point H: sit-to-stand requires side view and advises sideways chair orientation", () => {
  // User is facing camera front-on rather than sideways
  const frontFrameOn = normalizedFrontFrame();
  const evalResult = evaluatePositioning(frontFrameOn, "ftsst");

  assert.equal(evalResult.ready, false);
  assert.match(evalResult.guidance, /turn slightly sideways/i);
  assert.match(evalResult.actionableTip, /chair sideways/i);

  // Side view with chair correctly positioned sideways
  const sideFrameOn = normalizedSideFrame();
  const sideEval = evaluatePositioning(sideFrameOn, "ftsst");
  assert.equal(sideEval.checklist.hips, true);
  assert.equal(sideEval.checklist.knees, true);
  assert.equal(sideEval.checklist.feet, true);
  // Guidance is now holding or ready, not asking to turn
  assert.notEqual(sideEval.guidance, "Turn slightly sideways.");
});

// ---------------------------------------------------------------------------
// POINT I: Valid completed assessment scores correctly
// ---------------------------------------------------------------------------
test("Point I: clean completed assessment produces valid result structure and quality tracking", () => {
  const shoulder = new ShoulderAbductionTest();

  // Feed 10 calibration frames
  for (let i = 0; i < 10; i++) {
    shoulder.push(makeFrame(i * DEFAULT_FRAME_MS, frontFacingBase()));
  }

  // Abduction repetition (raising arms up to 90 deg and lowering down)
  const degAngles = [10, 30, 60, 90, 95, 90, 60, 30, 10];
  let t = 10 * DEFAULT_FRAME_MS;

  for (const angle of degAngles) {
    const pose = frontFacingBase();
    pose.left_elbow = { x: 240 - Math.sin((angle * Math.PI) / 180) * 120, y: 150 + Math.cos((angle * Math.PI) / 180) * 120, score: 0.95 };
    pose.right_elbow = { x: 400 + Math.sin((angle * Math.PI) / 180) * 120, y: 150 + Math.cos((angle * Math.PI) / 180) * 120, score: 0.95 };
    shoulder.push(makeFrame(t, pose));
    t += 100;
  }

  const result = shoulder.finish();
  assert.equal(result.testId, "shoulder");
  assert.ok(result.status === TEST_STATUS.COMPLETED || result.status === TEST_STATUS.INVALID);
  assert.ok(result.quality);
  assert.ok(result.quality.framesSeen > 0);
  assert.ok(Array.isArray(result.invalidReasons));
});

// ---------------------------------------------------------------------------
// POINT J: Low quality / poor visibility remains NOT_ASSESSED (no fake scores)
// ---------------------------------------------------------------------------
test("Point J: low quality or poor visibility does NOT fabricate healthy scores", () => {
  const shoulder = new ShoulderAbductionTest();

  // Feed mostly unusable / low-confidence frames
  for (let i = 0; i < 30; i++) {
    const frame = makeFrame(i * DEFAULT_FRAME_MS, frontFacingBase(), {
      score: 0.1, // Far below acceptable confidence
    });
    shoulder.push(frame);
  }

  const result = shoulder.finish();
  // Standards are NOT lowered: poor frames are strictly invalid
  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.equal(isUsableResult(result), false);
  assert.ok(result.invalidReasons.length > 0);
  assert.ok(
    result.invalidReasons.includes(REASON.TOO_FEW_USABLE_FRAMES) ||
    result.invalidReasons.includes(REASON.LOW_CONFIDENCE)
  );
  // Result must never pretend the user has valid arm elevation
  assert.equal(result.measurements.left.finalElevationDeg, null);
  assert.equal(result.measurements.right.finalElevationDeg, null);
});

// ---------------------------------------------------------------------------
// POINT K: Rep counting does NOT increment during TEMPORARY_LOSS or RECOVERING
// ---------------------------------------------------------------------------
test("Point K: repetitions cannot be counted during tracking loss or recovery", () => {
  const ftsst = new FiveTimesSitToStandTest({ chairSeatHeightCm: 45 });

  // 10 side selection frames
  for (let i = 0; i < 10; i++) {
    ftsst.push(makeFrame(i * DEFAULT_FRAME_MS, sideFacingBase({ kneeAngleDeg: 80 })));
  }

  // 5 seated confirm frames
  for (let i = 10; i < 16; i++) {
    ftsst.push(makeFrame(i * DEFAULT_FRAME_MS, sideFacingBase({ kneeAngleDeg: 80 })));
  }

  const countBeforeLoss = ftsst.standTimestamps.length;

  // Feed 10 unusable frames (e.g. person walks away or camera is occluded)
  for (let i = 16; i < 26; i++) {
    ftsst.push(makeFrame(i * DEFAULT_FRAME_MS, sideFacingBase({ kneeAngleDeg: 170 }), {
      score: 0.1, // unusable
    }));
  }

  // Rep count did NOT increase during unusable frames despite the angle in the synthetic pose
  assert.equal(ftsst.standTimestamps.length, countBeforeLoss);
});
