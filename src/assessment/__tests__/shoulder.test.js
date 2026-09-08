/**
 * Test 1 - shoulder abduction logic, driven by synthetic pose sequences.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { ShoulderAbductionTest, SHOULDER_PHASE } from "../tests/shoulder/shoulderLogic.js";
import { REASON, TEST_STATUS } from "../config/protocol.js";
import {
  shoulderSequence,
  withLowConfidence,
  withMissingKeypoints,
  DEFAULT_FRAME_MS,
} from "../fixtures/syntheticPoses.js";

const CALIBRATION_FRAMES = 20;
const FRAMES_PER_REP = 56;

function run(frames) {
  const test1 = new ShoulderAbductionTest();
  const statuses = frames.map((frame) => test1.push(frame));

  return { test1, statuses };
}

test("three clean repetitions produce a completed result on both sides", () => {
  const frames = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const { test1 } = run(frames);

  assert.equal(test1.phase, SHOULDER_PHASE.MEASURING);
  assert.deepEqual(test1.repetitionCounts(), { left: 3, right: 3 });
  assert.equal(test1.hasEnoughRepetitions(), true);

  const result = test1.finish();

  assert.equal(result.testId, "shoulder");
  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.deepEqual(result.invalidReasons, []);

  // The reported value is the MEDIAN across repetitions, not the best one.
  assert.equal(result.measurements.left.finalElevationDeg, 150);
  assert.equal(result.measurements.right.finalElevationDeg, 140);
  assert.deepEqual(result.measurements.left.repetitionElevationsDeg, [150, 152, 148]);
  assert.equal(result.measurements.observableDifferenceDeg, 10);
  assert.equal(result.measurements.left.rejectedRepetitions, 0);
  assert.equal(result.measurements.definition.basis, "median_of_valid_repetition_peaks");
});

test("one unusually high repetition cannot become the reported measurement", () => {
  const frames = shoulderSequence({
    leftPeaks: [100, 170, 102],
    rightPeaks: [100, 100, 100],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const result = run(frames).test1.finish();

  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.equal(result.measurements.left.finalElevationDeg, 102);
  assert.deepEqual(result.measurements.left.repetitionElevationsDeg, [100, 170, 102]);
});

test("the reported value is a median of peaks, so it is not the mean", () => {
  const frames = shoulderSequence({
    leftPeaks: [60, 62, 150],
    rightPeaks: [60, 62, 150],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const result = run(frames).test1.finish();
  const mean = (60 + 62 + 150) / 3;

  assert.equal(result.measurements.left.finalElevationDeg, 62);
  assert.notEqual(result.measurements.left.finalElevationDeg, Math.round(mean * 10) / 10);
});

test("quality metadata is recorded and contains no pose data", () => {
  const frames = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const { quality } = run(frames).test1.finish();

  assert.equal(quality.framesSeen, frames.length);
  assert.equal(quality.framesUsable, frames.length);
  assert.equal(quality.usableFrameRatio, 1);
  assert.equal(quality.lowFps, false);
  assert.ok(Math.abs(quality.fps - 30) < 0.5, `expected about 30 fps, got ${quality.fps}`);
  assert.ok(quality.meanKeypointScore > 0.8);
  assert.deepEqual(quality.reasonCounts, {});

  // Quality is metadata about the recording, never the recording itself.
  assert.deepEqual(
    Object.keys(quality).sort(),
    [
      "framesSeen",
      "framesUsable",
      "usableFrameRatio",
      "fps",
      "lowFps",
      "meanKeypointScore",
      "longestPoseLossMs",
      "reasonCounts",
    ].sort()
  );
});

test("two repetitions is invalid, and stays invalid even though a value exists", () => {
  const frames = shoulderSequence({
    leftPeaks: [150, 152],
    rightPeaks: [140, 141],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const { test1 } = run(frames);

  assert.equal(test1.hasEnoughRepetitions(), false);

  const result = test1.finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.INSUFFICIENT_REPETITIONS));

  // Measurements are kept for inspection but the status keeps them out of use.
  assert.equal(result.measurements.left.finalElevationDeg, 151);
  assert.notEqual(result.status, TEST_STATUS.COMPLETED);
});

test("movement that never reaches the entry threshold yields no measurement at all", () => {
  const frames = shoulderSequence({
    leftPeaks: [40, 42, 38],
    rightPeaks: [40, 42, 38],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const result = run(frames).test1.finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.equal(result.measurements.left.repetitionCount, 0);

  // Null, not zero: no repetition was observed, so there is nothing to report.
  assert.equal(result.measurements.left.finalElevationDeg, null);
  assert.equal(result.measurements.observableDifferenceDeg, null);
});

test("low-confidence keypoints make frames unusable and are counted by reason", () => {
  const clean = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const frames = withLowConfidence(clean, ["left_elbow"], 0, 9);

  const result = run(frames).test1.finish();

  assert.equal(result.quality.reasonCounts[REASON.LOW_CONFIDENCE], 10);
  assert.equal(result.quality.framesUsable, frames.length - 10);

  // A short dropout early on does not destroy the run.
  assert.equal(result.status, TEST_STATUS.COMPLETED);
});

test("a long pose dropout invalidates the result", () => {
  const clean = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const frames = withMissingKeypoints(clean, ["left_shoulder"], 30, 90);

  const result = run(frames).test1.finish();

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.POSE_LOST));
  assert.equal(result.quality.reasonCounts[REASON.KEYPOINTS_MISSING], 61);
  assert.ok(result.quality.longestPoseLossMs > 1500);
});

test("excessive trunk lean discards frames without failing the whole test", () => {
  const total = CALIBRATION_FRAMES + 3 * FRAMES_PER_REP;
  const leanFrames = Array.from({ length: 8 }, (_, index) => total - 8 + index);

  const frames = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
    trunkLeanFrames: leanFrames,
  });

  assert.equal(frames.length, total);

  const result = run(frames).test1.finish();

  assert.equal(result.quality.reasonCounts[REASON.EXCESSIVE_TRUNK_LEAN], 8);
  assert.equal(result.status, TEST_STATUS.COMPLETED);
});

test("aborting marks the attempt invalid", () => {
  const frames = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const result = run(frames).test1.finish({ attempts: 2, aborted: true });

  assert.equal(result.status, TEST_STATUS.INVALID);
  assert.ok(result.invalidReasons.includes(REASON.ABORTED_BY_USER));
  assert.equal(result.attempts, 2);
});

test("guidance codes reflect why the current frame was rejected", () => {
  const clean = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const test1 = new ShoulderAbductionTest();

  test1.push(clean[0]);
  assert.equal(test1.currentGuidance(), "stand_still_briefly");

  const missing = withMissingKeypoints(clean, ["left_shoulder"], 1, 1)[1];

  test1.push(missing);
  assert.equal(test1.currentGuidance(), "step_back_into_frame");

  const faint = withLowConfidence(clean, ["left_elbow"], 2, 2)[2];

  test1.push(faint);
  assert.equal(test1.currentGuidance(), "improve_lighting");
});

test("reset returns the test to a clean state so a retry is independent", () => {
  const frames = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  const { test1 } = run(frames);

  assert.deepEqual(test1.repetitionCounts(), { left: 3, right: 3 });

  test1.reset();

  assert.equal(test1.phase, SHOULDER_PHASE.CALIBRATING);
  assert.deepEqual(test1.repetitionCounts(), { left: 0, right: 0 });
  assert.equal(test1.referenceMidHipX, null);
  assert.equal(test1.finish().quality.framesSeen, 0);
});

test("frames arrive at the interval the fixtures claim", () => {
  const frames = shoulderSequence({
    leftPeaks: [150],
    rightPeaks: [140],
    calibrationFrames: 2,
  });

  assert.ok(Math.abs(frames[1].timestamp - frames[0].timestamp - DEFAULT_FRAME_MS) < 1e-9);
});

test("natural sway during MEASURING (brief trunk lean under the relaxed threshold) still completes cleanly", () => {
  // A ~20.2 degree trunk lean (shift 70) spanning the top of the first
  // repetition's ramp, its whole hold, and the start of its way down - the
  // kind of momentary weight shift a real person makes at the top of a
  // raise. It exceeds the strict 18 degree CALIBRATING/pre-fix threshold but
  // stays under the relaxed 22 degree MEASURING threshold, so with the fix
  // these frames are kept and the true peak is captured. Before the fix,
  // dropping them would have frozen the detector's tracked peak at the
  // frame just before the lean began (~127.5 degrees, well short of the
  // true 150 degree peak) - this is the regression test proving the fix.
  const frames = shoulderSequence({
    leftPeaks: [150, 150, 150],
    rightPeaks: [140, 140, 140],
    calibrationFrames: CALIBRATION_FRAMES,
    trunkLeanFrames: [37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50],
    trunkLeanShift: 70,
  });

  const { test1 } = run(frames);

  assert.deepEqual(test1.repetitionCounts(), { left: 3, right: 3 });

  const result = test1.finish();

  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.deepEqual(result.invalidReasons, []);

  // Comfortably above the ~127.5 degree value a truncated peak would have
  // produced, and close to the true 150 degree target.
  assert.ok(
    result.measurements.left.repetitionElevationsDeg[0] > 145,
    `expected the first rep's peak to survive the sway, got ${result.measurements.left.repetitionElevationsDeg[0]}`
  );
});

test("a trunk lean beyond even the relaxed MEASURING threshold is still rejected", () => {
  // The fixture's built-in lean shift (~25.4 degrees) is well past both the
  // strict 18 degree and the relaxed 22 degree thresholds, proving the
  // MEASURING relaxation is a modest, bounded margin, not a removal of the
  // check - here placed mid-repetition rather than during the trailing rest
  // period, unlike the existing "discards frames" test above.
  const frames = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
    trunkLeanFrames: [37, 38, 39, 40, 41, 42],
  });

  const result = run(frames).test1.finish();

  assert.equal(result.quality.reasonCounts[REASON.EXCESSIVE_TRUNK_LEAN], 6);
});

test("missing or occluded hips are extrapolated from shoulders to allow seated/desktop testing", () => {
  const frames = shoulderSequence({
    leftPeaks: [150, 152, 148],
    rightPeaks: [140, 141, 139],
    calibrationFrames: CALIBRATION_FRAMES,
  });

  // Strip hips from every frame (simulating sitting at a desk where hips are below webcam view)
  const deskFrames = frames.map((frame) => {
    const kp = { ...frame.keypoints };
    delete kp.left_hip;
    delete kp.right_hip;
    return { ...frame, keypoints: kp };
  });

  const { test1 } = run(deskFrames);

  assert.deepEqual(test1.repetitionCounts(), { left: 3, right: 3 });
  assert.equal(test1.hasEnoughRepetitions(), true);

  const result = test1.finish();
  assert.equal(result.status, TEST_STATUS.COMPLETED);
  assert.equal(result.measurements.left.finalElevationDeg, 150);
  assert.equal(result.measurements.right.finalElevationDeg, 140);
});

