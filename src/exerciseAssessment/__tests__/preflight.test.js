/**
 * Camera readiness checks.
 *
 * The regression these exist for: the framing checks compared MoveNet's
 * PIXEL coordinates against fractions of the frame (`ankle.y > 0.95`), so
 * for any real body the "whole body in frame" check failed on every frame,
 * readiness never became true, and Begin recording stayed permanently
 * disabled. The stability delta had the mirror-image fault: pixel movement
 * is never under 0.04, so the steady-position counter never advanced.
 *
 * Coordinates below are in pixels, matching what the pose engine actually
 * emits (see src/assessment/fixtures/syntheticPoses.js).
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  PREFLIGHT_CONFIDENCE,
  STABILITY_DELTA,
  calculatePoseDelta,
  evaluatePreflightChecklist,
} from "../preflight.js";

const SIZE = { width: 640, height: 480 };

/** A well-framed person standing in a 640x480 frame, facing the camera. */
function standingFrame(overrides = {}) {
  const point = (x, y, score = 0.9) => ({ x, y, score });

  return {
    keypoints: {
      left_shoulder: point(250, 140),
      right_shoulder: point(390, 140),
      left_elbow: point(235, 220),
      right_elbow: point(405, 220),
      left_wrist: point(228, 290),
      right_wrist: point(412, 290),
      left_hip: point(272, 270),
      right_hip: point(368, 270),
      left_knee: point(268, 350),
      right_knee: point(372, 350),
      left_ankle: point(265, 420),
      right_ankle: point(375, 420),
      ...overrides,
    },
  };
}

const FRONT = { signal: "hipFlexionAngleDeg" };
const SIDE = { signal: "kneeFlexionAngleDeg" };

test("a well-framed body in pixel coordinates is ready", () => {
  const result = evaluatePreflightChecklist(standingFrame(), FRONT, SIZE);

  assert.equal(result.ready, true);
  assert.deepEqual(result.checklist, {
    visible: true,
    orientation: true,
    margins: true,
    stable: false,
  });
});

test("the framing check is a fraction of the frame, not a raw pixel value", () => {
  // The old code compared y (≈420px) against 0.95 and always failed here.
  const ankleY = standingFrame().keypoints.left_ankle.y;

  assert.ok(ankleY > 0.95, "precondition: raw pixels exceed the old threshold");
  assert.equal(evaluatePreflightChecklist(standingFrame(), FRONT, SIZE).ready, true);
});

test("feet below the bottom of the frame still block readiness", () => {
  const cut = standingFrame({
    left_ankle: { x: 265, y: 474, score: 0.9 },
    right_ankle: { x: 375, y: 478, score: 0.9 },
  });
  const result = evaluatePreflightChecklist(cut, FRONT, SIZE);

  assert.equal(result.ready, false);
  assert.match(result.guidance, /Step back/);
  assert.equal(result.checklist.margins, false);
});

test("shoulders above the top of the frame still block readiness", () => {
  const clipped = standingFrame({
    left_shoulder: { x: 250, y: 12, score: 0.9 },
    right_shoulder: { x: 390, y: 10, score: 0.9 },
  });
  const result = evaluatePreflightChecklist(clipped, FRONT, SIZE);

  assert.equal(result.ready, false);
  assert.match(result.guidance, /camera tilt/);
});

test("a missing leg still blocks readiness for a full-body exercise", () => {
  const partial = standingFrame({
    left_ankle: { x: 265, y: 420, score: 0.1 },
    right_ankle: { x: 375, y: 420, score: 0.1 },
  });
  const result = evaluatePreflightChecklist(partial, FRONT, SIZE);

  assert.equal(result.ready, false);
  assert.match(result.guidance, /full body/);
  assert.equal(result.checklist.visible, false);
});

test("the confidence floor is unchanged at 0.55", () => {
  assert.equal(PREFLIGHT_CONFIDENCE, 0.55);

  const weak = standingFrame({
    left_knee: { x: 268, y: 350, score: 0.5 },
    right_knee: { x: 372, y: 350, score: 0.5 },
  });

  assert.equal(evaluatePreflightChecklist(weak, FRONT, SIZE).ready, false);
});

test("facing the camera is still required for a front-view exercise", () => {
  // Shoulders narrow relative to the torso: the user has turned side-on.
  const turned = standingFrame({
    left_shoulder: { x: 300, y: 140, score: 0.9 },
    right_shoulder: { x: 330, y: 140, score: 0.9 },
  });
  const result = evaluatePreflightChecklist(turned, FRONT, SIZE);

  assert.equal(result.ready, false);
  assert.match(result.guidance, /face the camera/i);
});

test("a side-view exercise refuses a square-on stance", () => {
  const result = evaluatePreflightChecklist(standingFrame(), SIDE, SIZE);

  assert.equal(result.ready, false);
  assert.match(result.guidance, /side-on/i);
});

test("an unknown frame size is reported rather than guessed at", () => {
  for (const size of [undefined, null, { width: 0, height: 0 }]) {
    const result = evaluatePreflightChecklist(standingFrame(), FRONT, size);

    assert.equal(result.ready, false);
    assert.match(result.guidance, /camera/i);
  }
});

test("holding still registers as still, in frame-relative units", () => {
  const first = standingFrame().keypoints;
  const second = standingFrame({
    left_shoulder: { x: 252, y: 141, score: 0.9 },
  }).keypoints;

  const delta = calculatePoseDelta(first, second, SIZE);

  assert.ok(delta < STABILITY_DELTA, `expected ${delta} under ${STABILITY_DELTA}`);
});

test("a real movement is not mistaken for holding still", () => {
  const first = standingFrame().keypoints;
  const second = standingFrame({
    left_shoulder: { x: 320, y: 200, score: 0.9 },
    right_shoulder: { x: 460, y: 200, score: 0.9 },
    left_hip: { x: 342, y: 330, score: 0.9 },
    right_hip: { x: 438, y: 330, score: 0.9 },
  }).keypoints;

  assert.ok(calculatePoseDelta(first, second, SIZE) > STABILITY_DELTA);
});

test("an unmeasurable delta counts as movement, never as stillness", () => {
  assert.equal(calculatePoseDelta(null, standingFrame().keypoints, SIZE), 1);
  assert.equal(calculatePoseDelta({}, {}, SIZE), 1);
  assert.equal(calculatePoseDelta(standingFrame().keypoints, standingFrame().keypoints, null), 1);
});
