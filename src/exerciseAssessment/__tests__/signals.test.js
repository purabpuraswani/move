/**
 * Tests for keypoints -> signal extraction.
 *
 * These are the numbers the rep counter and hold timer act on, so a wrong
 * value here becomes a miscounted repetition, not a cosmetic glitch. The
 * cases below are built from poses whose correct answer is known by
 * construction (a straight leg is 180 degrees; a horizontal thigh is 90),
 * plus the failure modes that matter: a low-confidence keypoint must produce
 * null rather than a number, and an unmeasurable exercise must refuse rather
 * than return zero.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  SignalNotAvailableError,
  UNSUPPORTED_SIGNALS,
  getSignalExtractor,
  hasSignalExtractor,
  supportedSignals,
} from "../signals.js";

/** A frame in the shape utils/keypoints.js toFrame() produces. */
function frameOf(points, score = 0.9) {
  const keypoints = {};

  for (const [name, [x, y]] of Object.entries(points)) {
    keypoints[name] = { x, y, score };
  }

  return { timestamp: 0, keypoints };
}

// A standing body, image coordinates, y increasing downward.
const STANDING = {
  left_shoulder: [100, 100],
  right_shoulder: [140, 100],
  left_hip: [105, 200],
  right_hip: [135, 200],
  left_knee: [105, 300],
  right_knee: [135, 300],
  left_ankle: [105, 400],
  right_ankle: [135, 400],
  left_elbow: [95, 150],
  right_elbow: [145, 150],
  left_wrist: [92, 200],
  right_wrist: [148, 200],
};

test("a straight leg reads as a fully extended knee", () => {
  const extract = getSignalExtractor("kneeExtensionAngleDeg");

  const angle = extract(frameOf(STANDING));

  assert.ok(Math.abs(angle - 180) < 1, `expected ~180, got ${angle}`);
});

test("a bent knee reads near 90 degrees", () => {
  const seated = {
    ...STANDING,
    left_knee: [105, 300],
    left_ankle: [205, 300],
    right_knee: [135, 300],
    right_ankle: [235, 300],
  };

  const angle = getSignalExtractor("kneeFlexionAngleDeg")(frameOf(seated));

  assert.ok(Math.abs(angle - 90) < 1, `expected ~90, got ${angle}`);
});

test("standing still is zero thigh elevation, a horizontal thigh is ninety", () => {
  const extract = getSignalExtractor("hipFlexionAngleDeg");

  assert.ok(Math.abs(extract(frameOf(STANDING)) - 0) < 1);

  const raised = { ...STANDING, left_knee: [205, 200], right_knee: [235, 200] };

  assert.ok(Math.abs(extract(frameOf(raised)) - 90) < 1);
});

test("hip extension reports zero when the leg swings forward, not backward", () => {
  const extract = getSignalExtractor("hipExtensionAngleDeg");

  // Shoulders right of the hips means the body faces right, so a knee further
  // right than the hip is in FRONT of the body -- flexion. Counting that as
  // extension would credit the user for the opposite movement.
  const forward = {
    ...STANDING,
    left_shoulder: [160, 100],
    right_shoulder: [200, 100],
    left_knee: [175, 280],
    right_knee: [205, 280],
  };

  assert.equal(extract(frameOf(forward)), 0);

  const backward = {
    ...STANDING,
    left_shoulder: [160, 100],
    right_shoulder: [200, 100],
    left_knee: [55, 280],
    right_knee: [85, 280],
  };

  assert.ok(extract(frameOf(backward)) > 10);
});

test("a straight arm reads as an extended elbow", () => {
  const angle = getSignalExtractor("elbowFlexionAngleDeg")(
    frameOf({
      ...STANDING,
      left_shoulder: [100, 100],
      left_elbow: [100, 150],
      left_wrist: [100, 200],
    }),
  );

  assert.ok(Math.abs(angle - 180) < 1, `expected ~180, got ${angle}`);
});

test("arm raised to horizontal reads about ninety degrees", () => {
  const raised = { ...STANDING, left_wrist: [0, 100], right_wrist: [240, 100] };

  const angle = getSignalExtractor("armElevationAngleDeg")(frameOf(raised));

  assert.ok(Math.abs(angle - 90) < 2, `expected ~90, got ${angle}`);
});

test("lifted foot height is a ratio of torso length, not pixels", () => {
  const extract = getSignalExtractor("liftedFootHeightRatio");

  assert.equal(extract(frameOf(STANDING)), 0);

  // Torso is 100px here; lifting one ankle 50px must read as 0.5.
  const lifted = { ...STANDING, left_ankle: [105, 350] };

  assert.ok(Math.abs(extract(frameOf(lifted)) - 0.5) < 0.01);

  // The same pose scaled by 2 must give the same ratio -- this is what makes
  // the threshold independent of camera distance and body size.
  const scaled = {};
  for (const [name, [x, y]] of Object.entries(lifted)) {
    scaled[name] = [x * 2, y * 2];
  }

  assert.ok(Math.abs(extract(frameOf(scaled)) - 0.5) < 0.01);
});

test("a low-confidence keypoint yields null, never a number", () => {
  const unsure = frameOf(STANDING, 0.05);

  for (const signal of supportedSignals()) {
    assert.equal(
      getSignalExtractor(signal)(unsure),
      null,
      `${signal} returned a value from keypoints below the confidence floor`,
    );
  }
});

test("a missing keypoint yields null rather than throwing", () => {
  const partial = frameOf({ left_shoulder: [100, 100], right_shoulder: [140, 100] });

  assert.equal(getSignalExtractor("kneeExtensionAngleDeg")(partial), null);
  assert.equal(getSignalExtractor("liftedFootHeightRatio")(partial), null);
});

test("the calf raise refuses to be measured instead of inventing a number", () => {
  // MoveNet has no heel or toe keypoint, so this cannot be observed. The
  // refusal must carry a reason the user can read -- returning 0 would look
  // like a failed exercise.
  assert.ok("heelRaiseAngleDeg" in UNSUPPORTED_SIGNALS);
  assert.equal(hasSignalExtractor("heelRaiseAngleDeg"), false);

  assert.throws(
    () => getSignalExtractor("heelRaiseAngleDeg"),
    (error) =>
      error instanceof SignalNotAvailableError && /heel/i.test(error.message),
  );
});

test("an unknown signal name refuses rather than returning undefined", () => {
  assert.throws(() => getSignalExtractor("notARealSignal"), SignalNotAvailableError);
});
