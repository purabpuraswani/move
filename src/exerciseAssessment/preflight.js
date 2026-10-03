/**
 * Camera readiness checks for an exercise session.
 *
 * Extracted from ExercisePage so the rules can be unit-tested against real
 * keypoint frames. Nothing here was loosened in the move: the same four
 * checks run in the same order, with the same intent.
 *
 * THE COORDINATE BUG THIS FIXES
 * -----------------------------
 * MoveNet returns keypoints in PIXELS of the video frame (the project's own
 * fixtures put a nose at x: 320, y: 110), and `toFrame` passes them through
 * unchanged — every measurement in src/assessment/ works in that space.
 *
 * The framing checks, however, compared those pixel values against
 * fractions: `ankle.y > 0.95` meant "ankle is in the bottom 5% of frame",
 * but against a pixel value like 450 it is true in every frame a body
 * appears in. The result was that `margins` never passed, readiness never
 * became true, and Begin recording stayed disabled forever — for all six
 * prescribed exercises, since each one is a full-body view. The stability
 * delta had the same problem in reverse: a pixel-space movement is never
 * below 0.04, so the steady-position counter could never climb either.
 *
 * The fix is to normalise against the real video size before comparing,
 * not to relax the thresholds. A frame whose size is unknown is reported
 * as not ready, because framing genuinely cannot be judged without it.
 */

import { shoulderTorsoRatio } from "../assessment/utils/geometry.js";

/** Minimum per-keypoint confidence for a joint to count as visible. */
export const PREFLIGHT_CONFIDENCE = 0.55;

/** Lower confidence floor for the four torso points the orientation ratio needs. */
export const TORSO_CONFIDENCE = 0.35;

/** How close to the frame edge a joint may sit, as a fraction of frame height. */
export const BOTTOM_MARGIN = 0.95;
export const TOP_MARGIN = 0.05;

/** Mean per-joint movement, as a fraction of frame size, still counted as "still". */
export const STABILITY_DELTA = 0.04;

/** Which way the user must face for a given measurement to mean anything. */
export const SIGNAL_ORIENTATION = {
  kneeExtensionAngleDeg: "side",
  kneeFlexionAngleDeg: "side",
  hipFlexionAngleDeg: "front",
  hipAbductionAngleDeg: "front",
  hipExtensionAngleDeg: "side",
  elbowFlexionAngleDeg: "side",
  armElevationAngleDeg: "front",
  liftedFootHeightRatio: "front",
};

/** How much of the body has to be in frame for the measurement to work. */
export const SIGNAL_BODY_SCOPE = {
  elbowFlexionAngleDeg: "upper",
  armElevationAngleDeg: "upper",
  kneeExtensionAngleDeg: "full",
  kneeFlexionAngleDeg: "full",
  hipFlexionAngleDeg: "full",
  hipAbductionAngleDeg: "full",
  hipExtensionAngleDeg: "full",
  liftedFootHeightRatio: "full",
};

const ARM_JOINTS_LEFT = ["left_shoulder", "left_elbow", "left_wrist"];
const ARM_JOINTS_RIGHT = ["right_shoulder", "right_elbow", "right_wrist"];
const LEG_JOINTS_LEFT = ["left_hip", "left_knee", "left_ankle"];
const LEG_JOINTS_RIGHT = ["right_hip", "right_knee", "right_ankle"];

const NOT_READY = (guidance, checklist) => ({ ready: false, guidance, checklist });

const EMPTY_CHECKS = { visible: false, orientation: false, margins: false, stable: false };

function confident(keypoint, floor = PREFLIGHT_CONFIDENCE) {
  return (keypoint?.score ?? 0) >= floor;
}

/**
 * The video's own pixel size, or null when it is not known yet.
 *
 * `getVideoSize()` reports 0 until the stream has produced a frame, and a
 * zero divisor would turn every coordinate into Infinity, so the caller is
 * told "not ready" rather than handed nonsense.
 */
export function normalisedSize(videoSize) {
  const width = videoSize?.width ?? 0;
  const height = videoSize?.height ?? 0;

  if (!width || !height) return null;

  return { width, height };
}

/**
 * Evaluate camera readiness for one frame.
 *
 * `videoSize` is `{ width, height }` in pixels, from the pose engine. It is
 * required: the framing checks are about where the body sits in the frame,
 * which is meaningless without knowing how big the frame is.
 */
export function evaluatePreflightChecklist(frame, config, videoSize) {
  if (!frame?.keypoints || !config) {
    return NOT_READY("Position yourself in front of the camera.", { ...EMPTY_CHECKS });
  }

  const size = normalisedSize(videoSize);

  if (!size) {
    return NOT_READY("Waiting for the camera to start…", { ...EMPTY_CHECKS });
  }

  const kp = frame.keypoints;
  const signal = config.signal;
  const orientationReq = SIGNAL_ORIENTATION[signal] || "front";
  const scope = SIGNAL_BODY_SCOPE[signal] || "full";

  // 1. Are the joints this measurement needs actually visible?
  if (scope === "upper") {
    const hasShoulders = confident(kp.left_shoulder) && confident(kp.right_shoulder);
    const hasAnArm =
      ARM_JOINTS_LEFT.every((joint) => confident(kp[joint])) ||
      ARM_JOINTS_RIGHT.every((joint) => confident(kp[joint]));

    if (!(hasShoulders && hasAnArm)) {
      return NOT_READY("Ensure your upper body and arms are clearly in view.", {
        ...EMPTY_CHECKS,
      });
    }
  } else {
    const hasShoulder = confident(kp.left_shoulder) || confident(kp.right_shoulder);
    const hasHips = confident(kp.left_hip) || confident(kp.right_hip);
    const hasALeg =
      LEG_JOINTS_LEFT.every((joint) => confident(kp[joint])) ||
      LEG_JOINTS_RIGHT.every((joint) => confident(kp[joint]));

    if (!(hasShoulder && hasHips && hasALeg)) {
      return NOT_READY("Step back so your full body (head to feet) is in view.", {
        ...EMPTY_CHECKS,
      });
    }
  }

  // 2. Framing. Normalised against the real frame height, so "the bottom
  //    5% of the picture" means that at any resolution.
  if (scope === "full") {
    const ankleY = Math.max(
      confident(kp.left_ankle) ? kp.left_ankle.y / size.height : 0,
      confident(kp.right_ankle) ? kp.right_ankle.y / size.height : 0,
    );

    if (ankleY > BOTTOM_MARGIN) {
      return NOT_READY("Step back to fit whole body into frame.", {
        ...EMPTY_CHECKS,
        visible: true,
      });
    }
  }

  const shoulderY = Math.min(
    confident(kp.left_shoulder) ? kp.left_shoulder.y / size.height : 1,
    confident(kp.right_shoulder) ? kp.right_shoulder.y / size.height : 1,
  );

  if (shoulderY < TOP_MARGIN) {
    return NOT_READY("Adjust camera tilt so your shoulders are within frame.", {
      ...EMPTY_CHECKS,
      visible: true,
    });
  }

  // 3. Orientation, from the shoulder-to-torso ratio. Scale-invariant, so
  //    it works directly in pixels and needs no normalisation.
  const hasTorso =
    confident(kp.left_shoulder, TORSO_CONFIDENCE) &&
    confident(kp.right_shoulder, TORSO_CONFIDENCE) &&
    confident(kp.left_hip, TORSO_CONFIDENCE) &&
    confident(kp.right_hip, TORSO_CONFIDENCE);

  if (hasTorso) {
    // The same geometry helper the assessment uses, unchanged.
    const ratio = shoulderTorsoRatio(
      kp.left_shoulder,
      kp.right_shoulder,
      kp.left_hip,
      kp.right_hip,
    );

    if (typeof ratio === "number" && Number.isFinite(ratio)) {
      if (orientationReq === "side" && ratio > 0.42) {
        return NOT_READY("Turn side-on to the camera.", {
          visible: true,
          orientation: false,
          margins: true,
          stable: false,
        });
      }

      if (orientationReq === "front" && ratio < 0.36) {
        return NOT_READY("Turn to face the camera directly.", {
          visible: true,
          orientation: false,
          margins: true,
          stable: false,
        });
      }
    }
  }

  return {
    ready: true,
    guidance: "Hold steady…",
    checklist: { visible: true, orientation: true, margins: true, stable: false },
  };
}

/**
 * Mean movement of the four torso joints between two frames, as a fraction
 * of frame size. Returns 1 (i.e. "moved a lot") when it cannot be computed,
 * so an unmeasurable frame never counts towards holding still.
 */
export function calculatePoseDelta(previousKeypoints, currentKeypoints, videoSize) {
  const size = normalisedSize(videoSize);

  if (!size || !previousKeypoints || !currentKeypoints) return 1;

  const joints = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"];
  let total = 0;
  let counted = 0;

  joints.forEach((joint) => {
    const previous = previousKeypoints[joint];
    const current = currentKeypoints[joint];

    if (!previous || !current) return;

    const dx = (current.x - previous.x) / size.width;
    const dy = (current.y - previous.y) / size.height;

    total += Math.hypot(dx, dy);
    counted += 1;
  });

  return counted > 0 ? total / counted : 1;
}
