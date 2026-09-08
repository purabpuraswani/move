/**
 * Plain-language text for the codes produced by the measurement logic.
 *
 * The logic stores codes, not sentences, so a stored result stays comparable and
 * can be re-worded later without being re-measured. This file is the only place
 * that turns a code into something a person reads.
 *
 * Wording rule: describe what the camera did or did not observe. Never describe
 * what it might mean about the person's health.
 */

import { REASON } from "../config/protocol.js";

const REASON_TEXT = {
  [REASON.KEYPOINTS_MISSING]: "Part of your body moved outside the camera view",
  [REASON.LOW_CONFIDENCE]: "The camera could not see your body clearly",
  [REASON.BOTH_SIDES_NOT_VISIBLE]: "Both sides of your body need to be visible",
  [REASON.NOT_FRONT_FACING]: "You turned away from facing the camera",
  [REASON.NOT_SIDE_FACING]: "The camera could not see your side view clearly",
  [REASON.EXCESSIVE_TRUNK_LEAN]: "Your upper body leaned more than this check allows",
  [REASON.HIP_SHIFT]: "Your hips moved sideways from where they started",
  [REASON.INSUFFICIENT_REPETITIONS]: "Not all repetitions were completed",
  [REASON.TOO_FEW_USABLE_FRAMES]: "We had trouble seeing your movement clearly",
  [REASON.POSE_LOST]: "Tracking was interrupted for too long",
  [REASON.LOW_FPS]: "The camera ran slowly on this device",
  [REASON.TIMEOUT]: "The check ran longer than its time limit",
  [REASON.FOOT_LOWERED]: "The lifted foot came back down",
  [REASON.SUPPORT_FOOT_MOVED]: "The supporting foot moved from where it started",
  [REASON.NO_VALID_POSITION]: "The starting position was not detected",
  [REASON.MAX_DURATION_REACHED]: "You reached the maximum time for this check",
  [REASON.ABORTED_BY_USER]: "You stopped this check",
  [REASON.CHAIR_HEIGHT_IMPLAUSIBLE]: "The chair height entered is outside the expected range",
};

/**
 * Returns ONE primary actionable suggestion to help the user succeed on retry.
 */
export function getActionableSuggestion(reasonCode, testType = "shoulder") {
  if (!reasonCode) return "Make sure your full body is in view and try again.";

  const code = reasonCode.includes(":") ? reasonCode.split(":")[1] : reasonCode;

  switch (code) {
    case REASON.KEYPOINTS_MISSING:
    case REASON.TOO_FEW_USABLE_FRAMES:
      return testType === "ftsst"
        ? "Move the camera farther back so your hips, knees, and feet stay in view."
        : "Step back so your full body stays inside the frame.";
    case REASON.POSE_LOST:
      return "Stay centered in the camera frame throughout the movement.";
    case REASON.LOW_CONFIDENCE:
      return "Turn on brighter lights or move away from windows behind you.";
    case REASON.NOT_FRONT_FACING:
      return "Face the camera directly with both shoulders visible.";
    case REASON.NOT_SIDE_FACING:
      return "Place your chair sideways so the camera sees your side profile.";
    case REASON.EXCESSIVE_TRUNK_LEAN:
      return "Keep your upper body upright as you move.";
    case REASON.HIP_SHIFT:
      return "Keep your hips centered and avoid swaying sideways.";
    case REASON.NO_VALID_POSITION:
      return testType === "ftsst"
        ? "Sit down on the chair first so your starting position can be seen."
        : "Get into position and hold still before starting.";
    default:
      return "Keep your body inside the outline and try again.";
  }
}

/**
 * A combined balance reason arrives namespaced as "right:pose_lost", because one
 * side can fail while the other succeeds.
 */
export function describeReason(code) {
  if (!code) return null;

  const separator = code.indexOf(":");

  if (separator > 0) {
    const side = code.slice(0, separator);
    const reason = code.slice(separator + 1);

    return `${side === "left" ? "Left" : "Right"} leg: ${
      (REASON_TEXT[reason] || reason).charAt(0).toLowerCase()
    }${(REASON_TEXT[reason] || reason).slice(1)}`;
  }

  return REASON_TEXT[code] || code;
}

export function describeReasons(codes) {
  if (!codes || !codes.length) return [];

  return codes.map(describeReason);
}

const GUIDANCE_TEXT = {
  stand_still_briefly: "Stand still for a moment so your starting position can be recorded.",
  step_back_into_frame: "Step back so your whole body is inside the frame.",
  improve_lighting: "Try more light on you, or move away from a bright window behind you.",
  face_the_camera: "Turn to face the camera.",
  stand_upright: "Stand upright without leaning.",
  keep_hips_still: "Keep your hips still.",
  show_full_side_view: "Move so your whole side is inside the frame.",
  turn_side_on_to_camera: "Turn so the camera sees you from the side.",
  sit_down_to_begin: "Sit down on the chair to begin.",
  stand_when_ready: "Stand up when you are ready.",
  lift_one_foot: "Lift one foot when you feel steady.",
  hold_still: "Hold still for a moment...",
  lost_position_briefly: "We lost your position briefly. Stay in frame.",
  recovering_tracking: "Recovering tracking... hold steady.",
  move_farther: "Move a little farther from the camera.",
  move_closer: "Move a little closer.",
  step_back_feet: "Please step back so your feet are visible.",
  camera_higher: "Move the camera slightly higher.",
  turn_sideways: "Turn slightly sideways.",
  continue: null,
};

export function describeGuidance(code) {
  return GUIDANCE_TEXT[code] ?? null;
}

const END_REASON_TEXT = {
  [REASON.FOOT_LOWERED]: "the lifted foot came down",
  [REASON.EXCESSIVE_TRUNK_LEAN]: "the upper body leaned past the limit for this check",
  [REASON.SUPPORT_FOOT_MOVED]: "the supporting foot moved",
  [REASON.POSE_LOST]: "the camera lost track of you",
  [REASON.MAX_DURATION_REACHED]: "the maximum time was reached",
  [REASON.ABORTED_BY_USER]: "you stopped it",
  [REASON.NO_VALID_POSITION]: "the position was never detected",
};

export function describeEndReason(code) {
  if (!code) return null;

  return END_REASON_TEXT[code] || code;
}

const STATUS_TEXT = {
  completed: "Recorded",
  invalid: "Not usable",
  skipped: "Skipped",
  not_started: "Not attempted",
};

export function describeStatus(status) {
  return STATUS_TEXT[status] || status;
}

/** Format a millisecond duration for display, or a dash when there is none. */
export function formatSeconds(milliseconds, fractionDigits = 2) {
  if (typeof milliseconds !== "number" || !Number.isFinite(milliseconds)) return "—";

  return `${(milliseconds / 1000).toFixed(fractionDigits)} s`;
}

/** Format a degree measurement, or a dash when there is none. */
export function formatDegrees(degrees) {
  if (typeof degrees !== "number" || !Number.isFinite(degrees)) return "—";

  return `${degrees.toFixed(1)}°`;
}
