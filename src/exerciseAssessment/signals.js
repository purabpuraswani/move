/**
 * Keypoints -> one number, per exercise.
 *
 * This is the link config.js explicitly said was missing: each entry in
 * EXERCISE_ENGINE_CONFIG names a `signal`, but nothing turned a MoveNet frame
 * into that signal, so the engines could never be driven by a camera. Without
 * this module the whole exerciseAssessment/ package is unreachable code.
 *
 * Everything here is deterministic geometry on the image plane — no model, no
 * inference, nothing per-frame that could not be computed with a protractor.
 * That is deliberate: rep counting, hold timing and angle measurement are
 * exactly the work that must not go to an LLM.
 *
 * TWO HONEST CONSTRAINTS, stated rather than engineered around:
 *
 * 1. These are projections of a 3D movement onto a 2D image, as
 *    utils/geometry.js already says of the baseline tests. They describe what
 *    the camera can see, not an anatomical joint angle, and they assume the
 *    camera view each entry declares (`view`). A user filmed from the wrong
 *    angle produces a measurement that is wrong rather than merely noisy,
 *    which is why every extractor reports `null` rather than a number when the
 *    keypoints it needs are not confidently visible.
 *
 * 2. `supported-calf-raise` is NOT implemented here, and that is not an
 *    oversight. Its configured signal is a heel-raise angle, and MoveNet's
 *    17-keypoint model has no heel and no toe keypoint — the ankle is the
 *    lowest point it estimates. A heel lift of a few centimetres is therefore
 *    not observable, and any number produced for it would be an invention
 *    dressed as a measurement. It is listed in UNSUPPORTED_SIGNALS with its
 *    reason, and callers surface that reason instead of scoring the exercise.
 *
 * Every threshold that consumes these values lives in config.js and is, as
 * that file states, a system decision awaiting physio review. Nothing here
 * changes that status.
 */

import {
  elevationFromDown,
  jointAngle,
  torsoLength,
} from "../assessment/utils/geometry.js";
import { getKeypoint } from "../assessment/utils/keypoints.js";

/** Minimum MoveNet confidence before a keypoint is used in a measurement. */
export const MIN_KEYPOINT_SCORE = 0.3;

/**
 * Signals this project deliberately does not compute, and why.
 *
 * Kept as data rather than a comment so the UI can show the real reason to
 * the user instead of failing silently or, worse, showing a fabricated score.
 */
export const UNSUPPORTED_SIGNALS = Object.freeze({
  heelRaiseAngleDeg:
    "A heel raise cannot be measured from this camera setup: the pose model " +
    "estimates 17 body points and none of them is the heel or the toe, so " +
    "the lift itself is not visible to it. Count your repetitions yourself.",
});

/** Both sides of a paired keypoint, or null if either is not confident. */
function pair(frame, leftName, rightName) {
  const left = getKeypoint(frame, leftName, MIN_KEYPOINT_SCORE);
  const right = getKeypoint(frame, rightName, MIN_KEYPOINT_SCORE);

  if (!left || !right) return null;

  return { left, right };
}

/**
 * Pick the side the camera can see best.
 *
 * Most of these exercises are performed one side at a time, and the user is
 * not asked which. Choosing the side whose keypoints the model is most
 * confident about is more robust than assuming a side and silently measuring
 * the leg that is not moving.
 */
function bestSide(frame, names) {
  const score = (side) =>
    names
      .map((name) => getKeypoint(frame, `${side}_${name}`, 0)?.score ?? 0)
      .reduce((total, value) => total + value, 0);

  return score("left") >= score("right") ? "left" : "right";
}

function sideJoint(frame, side, name) {
  return getKeypoint(frame, `${side}_${name}`, MIN_KEYPOINT_SCORE);
}

/**
 * Interior knee angle: ~180 with the leg straight, ~90 sitting.
 *
 * Serves both `kneeExtensionAngleDeg` (sit-to-stand, watching it rise past
 * the enter threshold) and `kneeFlexionAngleDeg` (wall sit, watching it stay
 * inside a band). They are the same observable quantity read two ways, so
 * they share one extractor rather than two that could drift apart.
 */
function kneeAngle(frame) {
  const side = bestSide(frame, ["hip", "knee", "ankle"]);

  const hip = sideJoint(frame, side, "hip");
  const knee = sideJoint(frame, side, "knee");
  const ankle = sideJoint(frame, side, "ankle");

  if (!hip || !knee || !ankle) return null;

  return jointAngle(hip, knee, ankle);
}

/** Thigh elevation from hanging-down: 0 standing, ~90 with thigh horizontal. */
function thighElevation(frame) {
  const side = bestSide(frame, ["hip", "knee"]);

  const hip = sideJoint(frame, side, "hip");
  const knee = sideJoint(frame, side, "knee");

  if (!hip || !knee) return null;

  return elevationFromDown(hip, knee);
}

const EXTRACTORS = {
  kneeExtensionAngleDeg: kneeAngle,
  kneeFlexionAngleDeg: kneeAngle,

  // Knee raise (front or side view): the thigh swings up from vertical.
  hipFlexionAngleDeg: thighElevation,

  // Side leg raise (front view): the same thigh-from-vertical quantity. In a
  // frontal view that deviation is abduction; the extractor cannot tell a
  // front view from a side view, which is why the view is declared per
  // exercise and shown to the user as setup guidance.
  hipAbductionAngleDeg: thighElevation,

  // Hip extension (side view): the leg travels BEHIND the body. Unsigned
  // elevation cannot tell behind from in front, so the horizontal direction
  // of the knee relative to the hip is used to keep only backward movement
  // and report forward movement as zero rather than as extension.
  hipExtensionAngleDeg: (frame) => {
    const side = bestSide(frame, ["hip", "knee"]);

    const hip = sideJoint(frame, side, "hip");
    const knee = sideJoint(frame, side, "knee");
    const shoulder = sideJoint(frame, side, "shoulder");

    if (!hip || !knee || !shoulder) return null;

    const elevation = elevationFromDown(hip, knee);

    if (elevation === null) return null;

    // Facing direction is inferred from the trunk's own lean, so the
    // measurement does not depend on the user standing on a particular side
    // of the frame.
    const forwardSign = Math.sign(shoulder.x - hip.x) || 1;
    const kneeOffset = (knee.x - hip.x) * forwardSign;

    // Knee ahead of the hip is flexion, not extension. Reported as 0 so a
    // forward swing can never be counted as a backward one.
    return kneeOffset > 0 ? 0 : elevation;
  },

  // Wall push-up: interior elbow angle, ~180 arms straight, smaller bent.
  elbowFlexionAngleDeg: (frame) => {
    const side = bestSide(frame, ["shoulder", "elbow", "wrist"]);

    const shoulder = sideJoint(frame, side, "shoulder");
    const elbow = sideJoint(frame, side, "elbow");
    const wrist = sideJoint(frame, side, "wrist");

    if (!shoulder || !elbow || !wrist) return null;

    return jointAngle(shoulder, elbow, wrist);
  },

  // Shoulder raise: arm elevation from hanging down, the same observable the
  // baseline shoulder test uses.
  armElevationAngleDeg: (frame) => {
    const side = bestSide(frame, ["shoulder", "wrist"]);

    const shoulder = sideJoint(frame, side, "shoulder");
    const wrist = sideJoint(frame, side, "wrist");

    if (!shoulder || !wrist) return null;

    return elevationFromDown(shoulder, wrist);
  },

  /**
   * Single-leg stand: how far the lifted foot is off the ground, as a
   * fraction of torso length.
   *
   * Expressed as a ratio, not pixels, so it means the same thing whatever the
   * user's height or distance from the camera -- the same normalisation
   * geometry.js already uses for the baseline tests.
   */
  liftedFootHeightRatio: (frame) => {
    const ankles = pair(frame, "left_ankle", "right_ankle");
    const shoulders = pair(frame, "left_shoulder", "right_shoulder");
    const hips = pair(frame, "left_hip", "right_hip");

    if (!ankles || !shoulders || !hips) return null;

    const torso = torsoLength(
      shoulders.left,
      shoulders.right,
      hips.left,
      hips.right,
    );

    if (!torso) return null;

    // y increases downward, so the higher foot has the smaller y. The gap
    // between the ankles is the lift, whichever foot was raised.
    return Math.abs(ankles.left.y - ankles.right.y) / torso;
  },
};

export class SignalNotAvailableError extends Error {}

/**
 * The extractor for one signal name.
 *
 * Throws for a signal this project has decided not to measure, carrying the
 * user-facing reason, so a caller cannot accidentally treat "we do not
 * measure this" as "the user scored zero".
 */
export function getSignalExtractor(signalName) {
  if (signalName in UNSUPPORTED_SIGNALS) {
    const error = new SignalNotAvailableError(UNSUPPORTED_SIGNALS[signalName]);
    error.signalName = signalName;

    throw error;
  }

  const extractor = EXTRACTORS[signalName];

  if (!extractor) {
    throw new SignalNotAvailableError(
      `no signal extractor is defined for "${signalName}"`,
    );
  }

  return extractor;
}

export function hasSignalExtractor(signalName) {
  return signalName in EXTRACTORS;
}

/** Signal names this module can genuinely measure. */
export function supportedSignals() {
  return Object.keys(EXTRACTORS);
}
