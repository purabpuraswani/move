/**
 * Reusable frame validation and quality accounting.
 *
 * Validation answers one question: can this frame contribute to a measurement?
 * A frame that cannot is excluded and its reason recorded. These are
 * engineering checks on what the camera could see. They are not clinical
 * observations and they do not describe the person's movement quality.
 */

import { POSE, REASON } from "../config/protocol.js";
import { shoulderTorsoRatio, tiltFromVertical, distance, midpoint } from "./geometry.js";
import { getKeypoints, missingKeypoints, meanScore } from "./keypoints.js";

/** Keypoint sets each test cannot operate without. */
export const REQUIRED_KEYPOINTS = {
  shoulder: [
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_hip",
    "right_hip",
  ],
  ftsstLeft: ["left_shoulder", "left_hip", "left_knee", "left_ankle"],
  ftsstRight: ["right_shoulder", "right_hip", "right_knee", "right_ankle"],
  balance: [
    "left_shoulder",
    "right_shoulder",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
  ],
};

/**
 * @typedef {object} FrameCheck
 * @property {boolean} usable
 * @property {string[]} reasons reason codes, empty when usable
 * @property {object|null} points the resolved keypoints when usable
 */

/** Confidence and presence check for a named keypoint set. */
export function checkRequiredKeypoints(frame, names, minScore = POSE.minRequiredKeypointScore) {
  const points = getKeypoints(frame, names, minScore);

  if (points) return { usable: true, reasons: [], points };

  const missing = missingKeypoints(frame, names, minScore);
  const anyAbsent = missing.some((name) => !frame?.keypoints?.[name]);

  return {
    usable: false,
    reasons: [anyAbsent ? REASON.KEYPOINTS_MISSING : REASON.LOW_CONFIDENCE],
    points: null,
    missing,
  };
}

/**
 * Front-facing torso check for tests 1 and 3.
 * A torso turned away from the camera narrows the shoulder line.
 */
export function checkFrontFacing(points, minRatio) {
  const ratio = shoulderTorsoRatio(
    points.left_shoulder,
    points.right_shoulder,
    points.left_hip,
    points.right_hip
  );

  if (ratio === null) {
    return { usable: false, reasons: [REASON.KEYPOINTS_MISSING], ratio: null };
  }

  return {
    usable: ratio >= minRatio,
    reasons: ratio >= minRatio ? [] : [REASON.NOT_FRONT_FACING],
    ratio,
  };
}

/** Side-facing check for test 2: the shoulder line should appear narrow. */
export function checkSideFacing(points, maxRatio) {
  const ratio = shoulderTorsoRatio(
    points.left_shoulder,
    points.right_shoulder,
    points.left_hip,
    points.right_hip
  );

  if (ratio === null) {
    return { usable: true, reasons: [], ratio: null };
  }

  return {
    usable: ratio <= maxRatio,
    reasons: ratio <= maxRatio ? [] : [REASON.NOT_SIDE_FACING],
    ratio,
  };
}

/** Trunk lean away from vertical, mid-hip to mid-shoulder. */
export function checkTrunkLean(points, maxDegrees) {
  const lean = tiltFromVertical(
    midpoint(points.left_shoulder, points.right_shoulder),
    midpoint(points.left_hip, points.right_hip)
  );

  if (lean === null) {
    return { usable: false, reasons: [REASON.KEYPOINTS_MISSING], lean: null };
  }

  return {
    usable: lean <= maxDegrees,
    reasons: lean <= maxDegrees ? [] : [REASON.EXCESSIVE_TRUNK_LEAN],
    lean,
  };
}

/**
 * Horizontal drift of the mid-hip from a reference position, expressed as a
 * fraction of shoulder width so it does not depend on camera distance.
 */
export function checkHipShift(points, referenceMidHipX, maxRatio) {
  if (referenceMidHipX === null || referenceMidHipX === undefined) {
    return { usable: true, reasons: [], shiftRatio: null };
  }

  const shoulderWidth = distance(points.left_shoulder, points.right_shoulder);

  if (shoulderWidth === 0) {
    return { usable: true, reasons: [], shiftRatio: null };
  }

  const midHip = midpoint(points.left_hip, points.right_hip);
  const shiftRatio = Math.abs(midHip.x - referenceMidHipX) / shoulderWidth;

  return {
    usable: shiftRatio <= maxRatio,
    reasons: shiftRatio <= maxRatio ? [] : [REASON.HIP_SHIFT],
    shiftRatio,
  };
}

/** Combine several check results into one. */
export function combineChecks(...checks) {
  const reasons = [];
  let usable = true;

  for (const check of checks) {
    if (!check) continue;

    if (!check.usable) usable = false;

    for (const reason of check.reasons || []) {
      if (!reasons.includes(reason)) reasons.push(reason);
    }
  }

  return { usable, reasons };
}

/** Tracking state machine states for user-friendly guidance and recovery. */
export const TRACKING_STATE = {
  TRACKING: "tracking",
  TEMPORARY_LOSS: "temporary_loss",
  RECOVERING: "recovering",
  FAILED: "failed",
};

export const RECOVERY_CONFIRMATION_FRAMES = 3;

/**
 * Accumulates per-frame outcomes for a single test run so the stored result can
 * say how good the recording was, without storing the recording.
 */
export class QualityTracker {
  constructor({ trackedKeypoints = [] } = {}) {
    this.trackedKeypoints = trackedKeypoints;
    this.reset();
  }

  reset() {
    this.framesSeen = 0;
    this.framesUsable = 0;
    this.reasonCounts = {};
    this.scoreSum = 0;
    this.firstTimestamp = null;
    this.lastTimestamp = null;
    this.consecutiveUnusableMs = 0;
    this.lastUnusableTimestamp = null;
    this.longestPoseLossMs = 0;
    this.trackingState = TRACKING_STATE.TRACKING;
    this.consecutiveUsableFrames = 0;
    this.recentWindow = [];
    this.recentWindowSize = 30;
  }

  /**
   * Record a frame outcome.
   * @returns {{poseLostFor: number, trackingState: string, recentUsableRatio: number}}
   */
  record(frame, usable, reasons = []) {
    this.framesSeen += 1;

    if (this.firstTimestamp === null) this.firstTimestamp = frame.timestamp;
    this.lastTimestamp = frame.timestamp;

    if (this.trackedKeypoints.length) {
      this.scoreSum += meanScore(frame, this.trackedKeypoints);
    }

    this.recentWindow.push(Boolean(usable));
    if (this.recentWindow.length > this.recentWindowSize) {
      this.recentWindow.shift();
    }

    if (usable) {
      this.framesUsable += 1;
      this.consecutiveUnusableMs = 0;
      this.lastUnusableTimestamp = null;

      if (
        this.trackingState === TRACKING_STATE.TEMPORARY_LOSS ||
        this.trackingState === TRACKING_STATE.RECOVERING
      ) {
        this.consecutiveUsableFrames += 1;
        if (this.consecutiveUsableFrames >= RECOVERY_CONFIRMATION_FRAMES) {
          this.trackingState = TRACKING_STATE.TRACKING;
        } else {
          this.trackingState = TRACKING_STATE.RECOVERING;
        }
      } else if (this.trackingState !== TRACKING_STATE.FAILED) {
        this.trackingState = TRACKING_STATE.TRACKING;
        this.consecutiveUsableFrames += 1;
      }
    } else {
      this.consecutiveUsableFrames = 0;
      for (const reason of reasons) {
        this.reasonCounts[reason] = (this.reasonCounts[reason] || 0) + 1;
      }

      if (this.lastUnusableTimestamp === null) {
        this.lastUnusableTimestamp = frame.timestamp;
        this.consecutiveUnusableMs = 0;
      } else {
        this.consecutiveUnusableMs = frame.timestamp - this.lastUnusableTimestamp;
      }

      this.longestPoseLossMs = Math.max(this.longestPoseLossMs, this.consecutiveUnusableMs);

      if (this.consecutiveUnusableMs > POSE.maxPoseLossMs) {
        this.trackingState = TRACKING_STATE.FAILED;
      } else {
        this.trackingState = TRACKING_STATE.TEMPORARY_LOSS;
      }
    }

    return {
      poseLostFor: this.consecutiveUnusableMs,
      trackingState: this.trackingState,
      recentUsableRatio: this.recentUsableRatio(),
    };
  }

  recentUsableRatio() {
    if (!this.recentWindow.length) return 1;
    const usableCount = this.recentWindow.filter(Boolean).length;
    return usableCount / this.recentWindow.length;
  }

  getTrackingState() {
    return this.trackingState;
  }

  durationMs() {
    if (this.firstTimestamp === null || this.lastTimestamp === null) return 0;

    return this.lastTimestamp - this.firstTimestamp;
  }

  fps() {
    const duration = this.durationMs();

    if (duration <= 0 || this.framesSeen < 2) return null;

    return (this.framesSeen - 1) / (duration / 1000);
  }

  usableFrameRatio() {
    if (!this.framesSeen) return 0;

    return this.framesUsable / this.framesSeen;
  }

  meanKeypointScore() {
    if (!this.framesSeen || !this.trackedKeypoints.length) return null;

    return this.scoreSum / this.framesSeen;
  }

  /** Serialisable summary. Contains no keypoints and no frame data. */
  summary() {
    const fps = this.fps();

    return {
      framesSeen: this.framesSeen,
      framesUsable: this.framesUsable,
      usableFrameRatio: Number(this.usableFrameRatio().toFixed(3)),
      fps: fps === null ? null : Number(fps.toFixed(1)),
      lowFps: fps !== null && fps < POSE.lowFpsThreshold,
      meanKeypointScore:
        this.meanKeypointScore() === null
          ? null
          : Number(this.meanKeypointScore().toFixed(3)),
      longestPoseLossMs: Math.round(this.longestPoseLossMs),
      reasonCounts: { ...this.reasonCounts },
    };
  }

  /** Quality-derived reasons that make a whole test result unusable. */
  blockingReasons() {
    const reasons = [];

    if (this.framesSeen && this.usableFrameRatio() < POSE.minUsableFrameRatio) {
      reasons.push(REASON.TOO_FEW_USABLE_FRAMES);
    }

    if (this.longestPoseLossMs > POSE.maxPoseLossMs) {
      reasons.push(REASON.POSE_LOST);
    }

    return reasons;
  }
}
