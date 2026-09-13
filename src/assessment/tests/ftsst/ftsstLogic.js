/**
 * Test 2 - five times sit-to-stand. Side-facing camera.
 *
 * WHAT IS MEASURED
 * The number of stands detected and the elapsed time from leaving the seated
 * position to reaching the fifth stand, using the knee angle (hip-knee-ankle)
 * as it appears in the camera image.
 *
 * WHAT IS NOT MEASURED
 * This is not equivalent to a clinician administering the test with a
 * stopwatch. Timing here starts and stops on automatic threshold crossings, not
 * on a human judgement of when movement began and ended, and the chair, floor,
 * footwear, and camera placement are uncontrolled. It measures neither leg
 * strength nor fall risk.
 *
 * The knee angle is used in preference to pixel heights because an angle does
 * not have to be rescaled for the person's size or their distance from
 * the camera.
 */

import { FTSST, POSE, REASON } from "../../config/protocol.js";
import { jointAngle, round } from "../../utils/geometry.js";
import { MedianFilter } from "../../utils/smoothing.js";
import { RepetitionDetector, REP_EVENT } from "../../utils/peaks.js";
import { measuredResult } from "../../utils/results.js";
import { getKeypoints, meanScore } from "../../utils/keypoints.js";
import {
  REQUIRED_KEYPOINTS,
  QualityTracker,
  checkRequiredKeypoints,
  checkSideFacing,
  combineChecks,
} from "../../utils/validation.js";

export const FTSST_PHASE = {
  SELECTING_SIDE: "selecting_side",
  WAITING_FOR_SEATED: "waiting_for_seated",
  READY: "ready",
  RISING: "rising",
  STANDING: "standing",
  DESCENDING: "descending",
  DONE: "done",
};

const ORIENTATION_KEYPOINTS = [
  "left_shoulder",
  "right_shoulder",
  "left_hip",
  "right_hip",
];

/** Frames of seated knee angle required before timing may begin. */
const SEATED_CONFIRM_FRAMES = 5;

/** Frames used to decide which side of the body the camera can see best. */
const SIDE_SELECTION_FRAMES = 10;

export class FiveTimesSitToStandTest {
  /**
   * @param {object} options
   * @param {number|null} options.chairSeatHeightCm collected before the test starts
   * @param {object} [options.config]
   */
  constructor({ chairSeatHeightCm = null, config = FTSST } = {}) {
    this.config = config;
    this.chairSeatHeightCm = chairSeatHeightCm;
    this.reset();
  }

  reset() {
    this.phase = FTSST_PHASE.SELECTING_SIDE;

    this.quality = new QualityTracker({
      trackedKeypoints: [...REQUIRED_KEYPOINTS.ftsstLeft, ...REQUIRED_KEYPOINTS.ftsstRight],
      maxRecoveryMs: this.config.maxRecoveryMs,
    });

    this.sideScores = { left: 0, right: 0 };
    this.sideSelectionFrames = 0;
    this.side = null;

    this.filter = new MedianFilter(this.config.smoothingWindow);

    this.detector = new RepetitionDetector({
      enterThreshold: this.config.standAngleDeg,
      exitThreshold: this.config.seatedAngleDeg,
      // A stand is counted the instant the angle crosses enterThreshold (see
      // REP_EVENT.ENTERED handling in push() below), so this floor cannot
      // reject that crossing directly. Instead a spike that immediately
      // falls back is later reported REJECTED (too_fast) once the excursion
      // completes, and push() retracts the provisional stand at that point.
      minDurationMs: this.config.minStandHoldMs,
      maxDurationMs: this.config.maxRepDurationMs,
      minSeparationMs: this.config.minRepDurationMs,
    });

    this.seatedFrames = 0;
    this.seatedConfirmed = false;

    this.startTimestamp = null;
    this.lastTimestamp = null;
    this.standTimestamps = [];
    this.completionTimeMs = null;
    this.timedOut = false;

    this.lastAngle = null;
    this.previousAngle = null;
    this.lastReasons = [];

    // Bounds SELECTING_SIDE + WAITING_FOR_SEATED so it cannot run forever;
    // see push().
    this.setupStartTimestamp = null;
    this.setupTimedOut = false;
  }

  /** Required keypoints for whichever side is in use. */
  #requiredKeypoints() {
    if (this.side === "right") return REQUIRED_KEYPOINTS.ftsstRight;

    return REQUIRED_KEYPOINTS.ftsstLeft;
  }

  push(frame) {
    this.lastTimestamp = frame.timestamp;

    if (this.setupTimedOut) return this.#status(true, []);

    if (this.setupStartTimestamp === null) this.setupStartTimestamp = frame.timestamp;

    // SELECTING_SIDE + WAITING_FOR_SEATED had no time limit: a person who
    // never settles into a confirmed seated position could feed an unbounded
    // number of frames into the quality accounting before a single repetition
    // is ever timed. Bound it explicitly. finish() already reports
    // NO_VALID_POSITION whenever seatedConfirmed is false, so this reuses
    // that same reason rather than a distinct code.
    if (
      !this.seatedConfirmed &&
      frame.timestamp - this.setupStartTimestamp >= this.config.maxSetupDurationMs
    ) {
      this.setupTimedOut = true;
      this.phase = FTSST_PHASE.DONE;

      return this.#status(true, []);
    }

    // Side selection happens first: whichever hip/knee/ankle chain the camera
    // sees more confidently is the one measured.
    if (this.phase === FTSST_PHASE.SELECTING_SIDE) {
      this.sideScores.left += meanScore(frame, REQUIRED_KEYPOINTS.ftsstLeft);
      this.sideScores.right += meanScore(frame, REQUIRED_KEYPOINTS.ftsstRight);
      this.sideSelectionFrames += 1;

      this.quality.record(frame, true, []);

      if (this.sideSelectionFrames >= SIDE_SELECTION_FRAMES) {
        this.side = this.sideScores.right > this.sideScores.left ? "right" : "left";
        this.phase = FTSST_PHASE.WAITING_FOR_SEATED;
      }

      return this.#status(true, []);
    }

    const keypointCheck = checkRequiredKeypoints(frame, this.#requiredKeypoints());

    if (!keypointCheck.usable) {
      return this.#recordUnusable(frame, keypointCheck.reasons);
    }

    const points = keypointCheck.points;

    // The side-facing check needs both shoulders and hips. In a true side view
    // the far-side keypoints are often weak, so it runs at the lower general
    // confidence floor and is skipped rather than failed when unavailable.
    const orientationPoints = getKeypoints(frame, ORIENTATION_KEYPOINTS, POSE.minKeypointScore);

    const orientation = orientationPoints
      ? checkSideFacing(orientationPoints, this.config.maxSideFacingRatio)
      : null;

    const combined = combineChecks(orientation);

    if (!combined.usable) {
      return this.#recordUnusable(frame, combined.reasons);
    }

    this.quality.record(frame, true, []);

    const prefix = this.side === "right" ? "right" : "left";

    const rawAngle = jointAngle(
      points[`${prefix}_hip`],
      points[`${prefix}_knee`],
      points[`${prefix}_ankle`]
    );

    const smoothed = this.filter.push(rawAngle);

    if (smoothed === null) return this.#status(true, []);

    this.previousAngle = this.lastAngle;
    this.lastAngle = smoothed;

    // A seated starting position has to be observed before the clock can start,
    // otherwise there is nothing meaningful to time from.
    if (!this.seatedConfirmed) {
      if (smoothed <= this.config.seatedAngleDeg) {
        this.seatedFrames += 1;

        if (this.seatedFrames >= SEATED_CONFIRM_FRAMES) {
          this.seatedConfirmed = true;
          this.phase = FTSST_PHASE.READY;

          // The usable-frame check in finish() must judge the rep-counting
          // segment, not side selection plus however long it took to sit
          // down and be confirmed seated. Restarting the tracker here scopes
          // quality.summary() and blockingReasons() to READY-onward.
          this.quality.reset();
        }
      } else {
        this.seatedFrames = 0;
      }

      return this.#status(true, []);
    }

    // Leaving the seated band starts the clock.
    if (this.startTimestamp === null) {
      if (smoothed > this.config.seatedAngleDeg) {
        this.startTimestamp = this.quality.activeTimestamp(frame.timestamp);
        this.phase = FTSST_PHASE.RISING;
      }

      return this.#status(true, []);
    }

    const activeTimestamp = this.quality.activeTimestamp(frame.timestamp);
    const outcome = this.detector.push(smoothed, activeTimestamp);

    if (outcome.event === REP_EVENT.ENTERED) {
      // Provisionally counted the instant the angle crosses standAngleDeg;
      // see the detector construction above for why REJECTED (below) must
      // retract this rather than the floor being enforced here.
      this.standTimestamps.push(activeTimestamp);

      if (
        this.standTimestamps.length >= this.config.requiredRepetitions &&
        this.completionTimeMs === null
      ) {
        this.completionTimeMs = activeTimestamp - this.startTimestamp;
      }
    } else if (outcome.event === REP_EVENT.REJECTED) {
      // The excursion that started with the last ENTERED turned out too
      // brief (a single-frame angle spike) or too slow to be a real stand.
      // Retract the provisional count instead of leaving a phantom
      // repetition, and undo completion if it was reached on the strength of
      // that phantom repetition.
      this.standTimestamps.pop();

      if (this.standTimestamps.length < this.config.requiredRepetitions) {
        this.completionTimeMs = null;
      }
    }

    if (
      this.completionTimeMs === null &&
      activeTimestamp - this.startTimestamp > this.config.maxTestDurationMs
    ) {
      this.timedOut = true;
    }

    this.phase = this.#derivePhase(smoothed);

    return this.#status(true, []);
  }

  #derivePhase(angle) {
    if (this.isComplete()) return FTSST_PHASE.DONE;

    if (angle >= this.config.standAngleDeg) return FTSST_PHASE.STANDING;

    if (this.previousAngle === null) return FTSST_PHASE.RISING;

    return angle >= this.previousAngle ? FTSST_PHASE.RISING : FTSST_PHASE.DESCENDING;
  }

  #recordUnusable(frame, reasons) {
    const { poseLostFor, trackingState, trackingWarning } = this.quality.record(frame, false, reasons);

    this.lastReasons = reasons;

    return {
      phase: this.phase,
      usable: false,
      reasons,
      side: this.side,
      kneeAngleDeg: this.lastAngle,
      repetitions: this.standTimestamps.length,
      elapsedMs: this.elapsedMs(),
      poseLostFor,
      trackingState,
      trackingWarning,
    };
  }

  #status(usable, reasons) {
    this.lastReasons = reasons;

    return {
      phase: this.phase,
      usable,
      reasons,
      side: this.side,
      kneeAngleDeg: this.lastAngle,
      repetitions: this.standTimestamps.length,
      elapsedMs: this.elapsedMs(),
      poseLostFor: 0,
      trackingState: this.quality.getTrackingState(),
      trackingWarning: this.quality.isTrackingWarning(),
    };
  }

  /**
   * Time since the person left the seat, for live display. Once the fifth stand
   * has been reached this is the measured completion time. It is derived from
   * frame timestamps, not wall-clock time.
   */
  elapsedMs() {
    if (this.startTimestamp === null) return 0;

    if (this.completionTimeMs !== null) return this.completionTimeMs;

    return Math.max(
      0,
      this.quality.activeTimestamp(this.lastTimestamp ?? this.startTimestamp) - this.startTimestamp
    );
  }

  /** True once the required number of stands has been reached. */
  isComplete() {
    return this.completionTimeMs !== null;
  }

  isTimedOut() {
    return this.timedOut;
  }

  isTrackingFailed() {
    return this.quality.isTrackingFailed();
  }

  finish({ attempts = 1, aborted = false } = {}) {
    this.phase = FTSST_PHASE.DONE;

    const invalidReasons = [...this.quality.blockingReasons()];

    if (aborted) invalidReasons.push(REASON.ABORTED_BY_USER);
    if (this.timedOut) invalidReasons.push(REASON.TIMEOUT);

    if (!this.seatedConfirmed) invalidReasons.push(REASON.NO_VALID_POSITION);

    if (this.standTimestamps.length < this.config.requiredRepetitions) {
      invalidReasons.push(REASON.INSUFFICIENT_REPETITIONS);
    }

    const setupWarnings = [];

    const chairHeightPlausible =
      typeof this.chairSeatHeightCm === "number" &&
      this.chairSeatHeightCm >= this.config.chairHeightMinCm &&
      this.chairSeatHeightCm <= this.config.chairHeightMaxCm;

    if (!chairHeightPlausible) {
      // Recorded as a setup warning rather than an invalid movement: the
      // repetitions were still performed and timed, but the seat height that
      // would be needed to compare two sessions is unreliable.
      setupWarnings.push(REASON.CHAIR_HEIGHT_IMPLAUSIBLE);
    }

    const measurements = {
      repetitionsDetected: this.standTimestamps.length,
      requiredRepetitions: this.config.requiredRepetitions,
      completionTimeMs: this.completionTimeMs,
      completionTimeSeconds: round(
        this.completionTimeMs === null ? null : this.completionTimeMs / 1000,
        2
      ),
      standTimestampsMs:
        this.startTimestamp === null
          ? []
          : this.standTimestamps.map((timestamp) => Math.round(timestamp - this.startTimestamp)),
      definition: {
        quantity: "observable_sit_to_stand_time",
        signal: "knee_angle_hip_knee_ankle",
        unit: "milliseconds",
        timingStartsOn: "departure_from_seated_knee_angle_band",
        timingEndsOn: this.config.timingEndsOn,
        plane: "camera_image_plane_projection",
        administration: "automatic_threshold_detection_not_clinician_timed",
      },
    };

    const setup = {
      chairSeatHeightCm: this.chairSeatHeightCm,
      chairSeatHeightPlausible: chairHeightPlausible,
      measuredSide: this.side,
      cameraView: "side",
      armsPosition: "folded_across_chest_instructed",
      warnings: setupWarnings,
    };

    return {
      ...measuredResult("ftsst", {
        valid: invalidReasons.length === 0,
        measurements,
        quality: this.quality.summary(),
        invalidReasons,
        attempts,
      }),
      setup,
    };
  }

  currentGuidance() {
    if (this.lastReasons.includes(REASON.KEYPOINTS_MISSING)) return "show_full_side_view";
    if (this.lastReasons.includes(REASON.LOW_CONFIDENCE)) return "improve_lighting";
    if (this.lastReasons.includes(REASON.NOT_SIDE_FACING)) return "turn_side_on_to_camera";
    if (this.phase === FTSST_PHASE.WAITING_FOR_SEATED) return "sit_down_to_begin";
    if (this.phase === FTSST_PHASE.READY) return "stand_when_ready";

    return "continue";
  }
}
