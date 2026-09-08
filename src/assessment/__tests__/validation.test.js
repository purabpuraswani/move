/**
 * Frame validation and quality accounting.
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  REQUIRED_KEYPOINTS,
  QualityTracker,
  checkRequiredKeypoints,
  checkFrontFacing,
  checkSideFacing,
  checkTrunkLean,
  checkHipShift,
  combineChecks,
} from "../utils/validation.js";
import { POSE, REASON, SHOULDER, FTSST } from "../config/protocol.js";
import { getKeypoint, getKeypoints, meanScore, toFrame, otherSide } from "../utils/keypoints.js";
import { frontFacingBase, sideFacingBase, makeFrame } from "../fixtures/syntheticPoses.js";

function frontFrame(overrides = {}) {
  return makeFrame(0, { ...frontFacingBase(), ...overrides });
}

test("toFrame keys a detector pose by name and defaults a missing score to zero", () => {
  const frame = toFrame(
    {
      keypoints: [
        { x: 1, y: 2, score: 0.8, name: "nose" },
        { x: 3, y: 4 },
      ],
    },
    123
  );

  assert.equal(frame.timestamp, 123);
  assert.deepEqual(frame.keypoints.nose, { x: 1, y: 2, score: 0.8 });
  // Second entry has no name, so it falls back to the COCO ordering.
  assert.deepEqual(frame.keypoints.left_eye, { x: 3, y: 4, score: 0 });
});

test("toFrame survives a detector returning nothing", () => {
  assert.deepEqual(toFrame(null, 5), { timestamp: 5, keypoints: {} });
  assert.deepEqual(toFrame({}, 5), { timestamp: 5, keypoints: {} });
});

test("getKeypoint rejects low scores and non-finite coordinates", () => {
  const frame = {
    timestamp: 0,
    keypoints: {
      nose: { x: 1, y: 1, score: 0.9 },
      left_eye: { x: 1, y: 1, score: 0.1 },
      right_eye: { x: Number.NaN, y: 1, score: 0.9 },
      left_ear: { x: "10", y: 1, score: 0.9 },
    },
  };

  assert.ok(getKeypoint(frame, "nose", 0.4));
  assert.equal(getKeypoint(frame, "left_eye", 0.4), null);
  assert.equal(getKeypoint(frame, "right_eye", 0.4), null);
  assert.equal(getKeypoint(frame, "left_ear", 0.4), null);
  assert.equal(getKeypoint(frame, "left_wrist", 0.4), null);
});

test("getKeypoints is all-or-nothing so partial data cannot be measured", () => {
  const frame = frontFrame();

  assert.ok(getKeypoints(frame, ["left_shoulder", "right_shoulder"], 0.4));
  assert.equal(getKeypoints(frame, ["left_shoulder", "nonexistent"], 0.4), null);
});

test("meanScore counts absent keypoints as zero rather than skipping them", () => {
  const frame = { timestamp: 0, keypoints: { nose: { x: 0, y: 0, score: 1 } } };

  assert.equal(meanScore(frame, ["nose"]), 1);
  assert.equal(meanScore(frame, ["nose", "left_eye"]), 0.5);
  assert.equal(meanScore(frame, []), 0);
});

test("otherSide flips the side", () => {
  assert.equal(otherSide("left"), "right");
  assert.equal(otherSide("right"), "left");
});

test("an absent keypoint and a faint keypoint are reported differently", () => {
  const complete = frontFrame();

  assert.equal(checkRequiredKeypoints(complete, REQUIRED_KEYPOINTS.shoulder).usable, true);

  const faint = frontFrame();

  faint.keypoints.left_elbow = { ...faint.keypoints.left_elbow, score: 0.05 };

  const faintCheck = checkRequiredKeypoints(faint, REQUIRED_KEYPOINTS.shoulder);

  assert.equal(faintCheck.usable, false);
  assert.deepEqual(faintCheck.reasons, [REASON.LOW_CONFIDENCE]);
  assert.deepEqual(faintCheck.missing, ["left_elbow"]);

  const absent = frontFrame();

  delete absent.keypoints.left_elbow;

  const absentCheck = checkRequiredKeypoints(absent, REQUIRED_KEYPOINTS.shoulder);

  assert.equal(absentCheck.usable, false);
  assert.deepEqual(absentCheck.reasons, [REASON.KEYPOINTS_MISSING]);
});

test("checkRequiredKeypoints handles a frame with no keypoints at all", () => {
  const check = checkRequiredKeypoints({ timestamp: 0, keypoints: {} }, REQUIRED_KEYPOINTS.balance);

  assert.equal(check.usable, false);
  assert.deepEqual(check.reasons, [REASON.KEYPOINTS_MISSING]);
  assert.equal(check.points, null);
});

test("a front-facing torso passes the front check and fails the side check", () => {
  const points = frontFrame().keypoints;

  const front = checkFrontFacing(points, SHOULDER.minFrontFacingRatio);

  assert.equal(front.usable, true);
  assert.ok(front.ratio > SHOULDER.minFrontFacingRatio);

  const side = checkSideFacing(points, FTSST.maxSideFacingRatio);

  assert.equal(side.usable, false);
  assert.deepEqual(side.reasons, [REASON.NOT_SIDE_FACING]);
});

test("a side-facing torso passes the side check and fails the front check", () => {
  const points = makeFrame(0, sideFacingBase(90)).keypoints;

  const side = checkSideFacing(points, FTSST.maxSideFacingRatio);

  assert.equal(side.usable, true);
  assert.ok(side.ratio < FTSST.maxSideFacingRatio);

  const front = checkFrontFacing(points, SHOULDER.minFrontFacingRatio);

  assert.equal(front.usable, false);
  assert.deepEqual(front.reasons, [REASON.NOT_FRONT_FACING]);
});

test("an unmeasurable orientation is skipped by the side check, not failed", () => {
  // Zero torso length: the ratio cannot be computed at all.
  const collapsed = {
    left_shoulder: { x: 10, y: 10 },
    right_shoulder: { x: 10, y: 10 },
    left_hip: { x: 10, y: 10 },
    right_hip: { x: 10, y: 10 },
  };

  const side = checkSideFacing(collapsed, FTSST.maxSideFacingRatio);

  assert.equal(side.usable, true);
  assert.equal(side.ratio, null);

  // The front check is stricter, because tests 1 and 3 depend on it.
  const front = checkFrontFacing(collapsed, SHOULDER.minFrontFacingRatio);

  assert.equal(front.usable, false);
  assert.deepEqual(front.reasons, [REASON.KEYPOINTS_MISSING]);
});

test("trunk lean is measured from mid-hip to mid-shoulder", () => {
  const upright = checkTrunkLean(frontFrame().keypoints, SHOULDER.maxTrunkLeanDeg);

  assert.equal(upright.usable, true);
  assert.ok(upright.lean < 1);

  const leaned = frontFrame({
    left_shoulder: { x: 240 + 120, y: 150 },
    right_shoulder: { x: 400 + 120, y: 150 },
  }).keypoints;

  const check = checkTrunkLean(leaned, SHOULDER.maxTrunkLeanDeg);

  assert.equal(check.usable, false);
  assert.deepEqual(check.reasons, [REASON.EXCESSIVE_TRUNK_LEAN]);
  assert.ok(check.lean > SHOULDER.maxTrunkLeanDeg);
});

test("hip shift is skipped until a reference position exists", () => {
  const points = frontFrame().keypoints;

  assert.deepEqual(checkHipShift(points, null, SHOULDER.maxHipShiftRatio), {
    usable: true,
    reasons: [],
    shiftRatio: null,
  });

  const atRest = checkHipShift(points, 320, SHOULDER.maxHipShiftRatio);

  assert.equal(atRest.usable, true);
  assert.equal(atRest.shiftRatio, 0);

  // Shifted by 80px against a 160px shoulder width: a ratio of 0.5.
  const shifted = checkHipShift(points, 240, SHOULDER.maxHipShiftRatio);

  assert.equal(shifted.usable, false);
  assert.equal(shifted.shiftRatio, 0.5);
  assert.deepEqual(shifted.reasons, [REASON.HIP_SHIFT]);
});

test("combineChecks collects every reason and ignores null checks", () => {
  const combined = combineChecks(
    { usable: true, reasons: [] },
    null,
    { usable: false, reasons: [REASON.HIP_SHIFT] },
    { usable: false, reasons: [REASON.HIP_SHIFT, REASON.NOT_FRONT_FACING] }
  );

  assert.equal(combined.usable, false);
  assert.deepEqual(combined.reasons, [REASON.HIP_SHIFT, REASON.NOT_FRONT_FACING]);
});

test("QualityTracker measures frame rate and flags a slow one", () => {
  const tracker = new QualityTracker({ trackedKeypoints: ["nose"] });

  for (let index = 0; index < 10; index += 1) {
    tracker.record({ timestamp: index * 100, keypoints: { nose: { x: 0, y: 0, score: 0.9 } } }, true);
  }

  const summary = tracker.summary();

  assert.equal(summary.framesSeen, 10);
  assert.equal(summary.framesUsable, 10);
  assert.equal(summary.usableFrameRatio, 1);
  assert.equal(summary.fps, 10);
  assert.equal(summary.lowFps, true);
  assert.equal(summary.meanKeypointScore, 0.9);
  assert.deepEqual(tracker.blockingReasons(), []);
});

test("QualityTracker refuses to report a frame rate it cannot know", () => {
  const tracker = new QualityTracker();

  assert.equal(tracker.summary().fps, null);
  assert.equal(tracker.summary().usableFrameRatio, 0);
  assert.equal(tracker.summary().meanKeypointScore, null);
  assert.deepEqual(tracker.blockingReasons(), []);

  tracker.record({ timestamp: 0, keypoints: {} }, true);

  assert.equal(tracker.summary().fps, null);
});

test("too many discarded frames blocks the whole result", () => {
  const tracker = new QualityTracker();

  for (let index = 0; index < 10; index += 1) {
    tracker.record({ timestamp: index * 33, keypoints: {} }, index < 5, [REASON.LOW_CONFIDENCE]);
  }

  assert.equal(tracker.summary().usableFrameRatio, 0.5);
  assert.ok(tracker.summary().usableFrameRatio < POSE.minUsableFrameRatio);
  assert.deepEqual(tracker.blockingReasons(), [REASON.TOO_FEW_USABLE_FRAMES]);
  assert.equal(tracker.summary().reasonCounts[REASON.LOW_CONFIDENCE], 5);
});

test("the longest unbroken dropout is tracked, not the total", () => {
  const tracker = new QualityTracker();
  const pattern = [
    // Two separate dropouts, the longer one lasting 5 frames.
    true, false, false, true, true, false, false, false, false, false, true,
  ];

  pattern.forEach((usable, index) => {
    tracker.record({ timestamp: index * 100, keypoints: {} }, usable, [REASON.POSE_LOST]);
  });

  // Five consecutive unusable frames 100ms apart span 400ms.
  assert.equal(tracker.summary().longestPoseLossMs, 400);
  assert.equal(tracker.summary().reasonCounts[REASON.POSE_LOST], 7);
});

test("a dropout longer than the ceiling blocks the result", () => {
  const tracker = new QualityTracker();

  for (let index = 0; index < 100; index += 1) {
    tracker.record({ timestamp: index * 100, keypoints: {} }, index >= 20, [REASON.POSE_LOST]);
  }

  assert.ok(tracker.summary().longestPoseLossMs > POSE.maxPoseLossMs);
  assert.ok(tracker.blockingReasons().includes(REASON.POSE_LOST));
});

test("the quality summary carries no keypoints, frames, or images", () => {
  const tracker = new QualityTracker({ trackedKeypoints: ["nose"] });

  tracker.record({ timestamp: 0, keypoints: { nose: { x: 1, y: 2, score: 0.9 } } }, true);

  const serialised = JSON.stringify(tracker.summary());

  for (const forbidden of ["keypoints", "frames\"", "video", "image", "\"x\"", "\"y\""]) {
    assert.ok(!serialised.includes(forbidden), `quality summary leaked ${forbidden}`);
  }
});
