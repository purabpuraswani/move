/**
 * Test 1 - bilateral active shoulder abduction. Front-facing camera.
 *
 * WHAT IS MEASURED
 * The angle of the shoulder-to-elbow segment away from the downward vertical,
 * as it appears in the camera image, at the peak of each repetition. Left and
 * right are measured independently and compared.
 *
 * WHAT IS NOT MEASURED
 * This is not clinical range of motion. It is a projection of a
 * three-dimensional movement onto a two-dimensional image, taken from a
 * consumer webcam, using the upper arm only. It does not measure joint health,
 * strength, or whether any movement limitation exists.
 *
 * This module is pure logic: it takes frames in and produces a result. It has
 * no knowledge of cameras, models, or React.
 */

import { REASON, SHOULDER } from "../../config/protocol.js";
import { elevationFromDown, midpoint, round, distance } from "../../utils/geometry.js";
import { median, MedianFilter } from "../../utils/smoothing.js";
import { RepetitionDetector } from "../../utils/peaks.js";
import { measuredResult } from "../../utils/results.js";
import {
  REQUIRED_KEYPOINTS,
  QualityTracker,
  checkRequiredKeypoints,
  checkFrontFacing,
  checkTrunkLean,
  checkHipShift,
  combineChecks,
} from "../../utils/validation.js";

export const SHOULDER_PHASE = {
  CALIBRATING: "calibrating",
  MEASURING: "measuring",
  DONE: "done",
};

export class ShoulderAbductionTest {
  constructor(config = SHOULDER) {
    this.config = config;
    this.reset();
  }

  reset() {
    this.phase = SHOULDER_PHASE.CALIBRATING;

    this.quality = new QualityTracker({
      trackedKeypoints: REQUIRED_KEYPOINTS.shoulder,
      maxRecoveryMs: this.config.maxRecoveryMs,
    });

    this.calibrationHipX = [];
    this.referenceMidHipX = null;

    this.filters = {
      left: new MedianFilter(this.config.smoothingWindow),
      right: new MedianFilter(this.config.smoothingWindow),
    };

    this.detectors = {
      left: this.#createDetector(),
      right: this.#createDetector(),
    };

    this.live = { left: null, right: null };
    this.lastReasons = [];
  }

  #createDetector() {
    return new RepetitionDetector({
      enterThreshold: this.config.repEnterAngleDeg,
      exitThreshold: this.config.repExitAngleDeg,
      minDurationMs: this.config.minRepDurationMs,
      maxDurationMs: this.config.maxRepDurationMs,
    });
  }

  /**
   * Extrapolates virtual hip positions if the user is seated or hips are occluded by a desk.
   * Consumer RGB webcams at desks routinely cut off below the chest. Upper arm elevation
   * only relies on shoulders and elbows; hips are only used for orientation reference.
   */
  #ensureHipKeypoints(frame) {
    if (!frame || !frame.keypoints) return frame;

    const kp = frame.keypoints;
    const minScore = this.config?.minRequiredKeypointScore ?? 0.4;

    const leftShoulder = kp.left_shoulder;
    const rightShoulder = kp.right_shoulder;
    const hasLeftShoulder = Boolean(leftShoulder && (leftShoulder.score ?? 1) >= minScore);
    const hasRightShoulder = Boolean(rightShoulder && (rightShoulder.score ?? 1) >= minScore);

    if (hasLeftShoulder && hasRightShoulder) {
      const shoulderWidth = distance(leftShoulder, rightShoulder);
      const hasLeftHip = Boolean(kp.left_hip && (kp.left_hip.score ?? 1) >= minScore);
      const hasRightHip = Boolean(kp.right_hip && (kp.right_hip.score ?? 1) >= minScore);

      if (!hasLeftHip || !hasRightHip) {
        const torsoDrop = shoulderWidth > 0 ? shoulderWidth * 1.2 : 0.35;
        let estLeftHipY = leftShoulder.y + torsoDrop;
        let estRightHipY = rightShoulder.y + torsoDrop;

        if (hasLeftHip && !hasRightHip) {
          estRightHipY = kp.left_hip.y;
        } else if (!hasLeftHip && hasRightHip) {
          estLeftHipY = kp.right_hip.y;
        }

        const newKeypoints = { ...kp };
        if (!hasLeftHip) {
          newKeypoints.left_hip = {
            x: leftShoulder.x,
            y: estLeftHipY,
            score: 0.85,
            estimated: true,
          };
        }
        if (!hasRightHip) {
          newKeypoints.right_hip = {
            x: rightShoulder.x,
            y: estRightHipY,
            score: 0.85,
            estimated: true,
          };
        }

        return {
          ...frame,
          keypoints: newKeypoints,
        };
      }
    }

    return frame;
  }

  /**
   * Feed one pose frame.
   *
   * @param {{timestamp: number, keypoints: object}} frame
   * @returns {{phase: string, usable: boolean, reasons: string[], live: object,
   *            repetitions: {left: number, right: number}, poseLostFor: number}}
   */
  push(frame) {
    const frameWithHips = this.#ensureHipKeypoints(frame);
    const keypointCheck = checkRequiredKeypoints(frameWithHips, REQUIRED_KEYPOINTS.shoulder);

    if (!keypointCheck.usable) {
      return this.#recordUnusable(frameWithHips, keypointCheck.reasons);
    }

    const points = keypointCheck.points;

    // CALIBRATING needs a clean baseline, so it keeps the strict thresholds.
    // MEASURING allows natural sway - a weight shift, a brief trunk lean,
    // momentary hip drift - that should not blank out an otherwise-good
    // frame mid-repetition and truncate a rep's peak. See config/protocol.js
    // for the modest, explicit margin used here.
    const measuring = this.phase === SHOULDER_PHASE.MEASURING;

    const orientation = checkFrontFacing(
      points,
      measuring ? this.config.minFrontFacingRatioMeasuring : this.config.minFrontFacingRatio
    );
    const lean = checkTrunkLean(
      points,
      measuring ? this.config.maxTrunkLeanDegMeasuring : this.config.maxTrunkLeanDeg
    );
    const hipShift = checkHipShift(
      points,
      this.referenceMidHipX,
      measuring ? this.config.maxHipShiftRatioMeasuring : this.config.maxHipShiftRatio
    );

    const combined = combineChecks(orientation, lean, hipShift);

    if (!combined.usable) {
      return this.#recordUnusable(frameWithHips, combined.reasons);
    }

    this.quality.record(frameWithHips, true, []);

    // Quiet standing at the start fixes the reference hip position that later
    // hip-shift checks are measured against.
    if (this.phase === SHOULDER_PHASE.CALIBRATING) {
      this.calibrationHipX.push(midpoint(points.left_hip, points.right_hip).x);

      if (this.calibrationHipX.length >= this.config.calibrationFrames) {
        this.referenceMidHipX = median(this.calibrationHipX);
        this.phase = SHOULDER_PHASE.MEASURING;
      }

      return this.#status(frame, true, []);
    }

    const angles = {
      left: elevationFromDown(points.left_shoulder, points.left_elbow),
      right: elevationFromDown(points.right_shoulder, points.right_elbow),
    };

    for (const side of ["left", "right"]) {
      const smoothed = this.filters[side].push(angles[side]);

      this.live[side] = smoothed;

      this.detectors[side].push(smoothed, this.quality.activeTimestamp(frame.timestamp));
    }

    return this.#status(frame, true, []);
  }

  #recordUnusable(frame, reasons) {
    const { poseLostFor, trackingState, trackingWarning } = this.quality.record(frame, false, reasons);

    this.lastReasons = reasons;

    return {
      phase: this.phase,
      usable: false,
      reasons,
      live: { ...this.live },
      repetitions: this.repetitionCounts(),
      poseLostFor,
      trackingState,
      trackingWarning,
    };
  }

  #status(frame, usable, reasons) {
    this.lastReasons = reasons;

    return {
      phase: this.phase,
      usable,
      reasons,
      live: { ...this.live },
      repetitions: this.repetitionCounts(),
      poseLostFor: 0,
      trackingState: this.quality.getTrackingState(),
      trackingWarning: this.quality.isTrackingWarning(),
    };
  }

  repetitionCounts() {
    return {
      left: this.detectors.left.validRepetitions().length,
      right: this.detectors.right.validRepetitions().length,
    };
  }

  /** True once both sides have enough accepted repetitions. */
  hasEnoughRepetitions() {
    const counts = this.repetitionCounts();

    return (
      counts.left >= this.config.requiredRepetitions &&
      counts.right >= this.config.requiredRepetitions
    );
  }

  isTrackingFailed() {
    return this.quality.isTrackingFailed();
  }

  /**
   * Produce the result. Never throws and never guesses: if the run did not meet
   * the requirements the result is returned with status "invalid" and the
   * reasons attached.
   */
  finish({ attempts = 1, aborted = false } = {}) {
    this.phase = SHOULDER_PHASE.DONE;

    const invalidReasons = [...this.quality.blockingReasons()];

    if (aborted) invalidReasons.push(REASON.ABORTED_BY_USER);

    const sides = {};

    for (const side of ["left", "right"]) {
      const peaks = this.detectors[side].peaks();

      sides[side] = {
        repetitionCount: peaks.length,
        // The median across repetitions is the reported value, so one unusually
        // high or low repetition cannot become the measurement.
        finalElevationDeg: round(median(peaks), 1),
        repetitionElevationsDeg: peaks.map((peak) => round(peak, 1)),
        rejectedRepetitions: this.detectors[side].rejected.length,
      };
    }

    if (!this.hasEnoughRepetitions() && !invalidReasons.includes(REASON.INSUFFICIENT_REPETITIONS)) {
      invalidReasons.push(REASON.INSUFFICIENT_REPETITIONS);
    }

    const bothMeasured =
      sides.left.finalElevationDeg !== null && sides.right.finalElevationDeg !== null;

    const measurements = {
      left: sides.left,
      right: sides.right,
      observableDifferenceDeg: bothMeasured
        ? round(Math.abs(sides.left.finalElevationDeg - sides.right.finalElevationDeg), 1)
        : null,
      requiredRepetitions: this.config.requiredRepetitions,
      // Recorded so a stored measurement stays interpretable if the definition
      // is ever revised.
      definition: {
        quantity: "observable_arm_elevation",
        segment: "shoulder_to_elbow",
        referenceAxis: "downward_vertical_image_plane",
        unit: "degrees",
        basis: "median_of_valid_repetition_peaks",
        plane: "camera_image_plane_projection",
      },
    };

    return measuredResult("shoulder", {
      valid: invalidReasons.length === 0,
      measurements,
      quality: this.quality.summary(),
      invalidReasons,
      attempts,
    });
  }

  /** Guidance code for the UI while the test is running. */
  currentGuidance() {
    if (this.lastReasons.includes(REASON.KEYPOINTS_MISSING)) return "step_back_into_frame";
    if (this.lastReasons.includes(REASON.LOW_CONFIDENCE)) return "improve_lighting";
    if (this.lastReasons.includes(REASON.NOT_FRONT_FACING)) return "face_the_camera";
    if (this.lastReasons.includes(REASON.EXCESSIVE_TRUNK_LEAN)) return "stand_upright";
    if (this.lastReasons.includes(REASON.HIP_SHIFT)) return "keep_hips_still";
    if (this.phase === SHOULDER_PHASE.CALIBRATING) return "stand_still_briefly";

    return "continue";
  }
}

// SHOULDER_MIN_FRAMES was defined but never imported or used anywhere in the
// app (dead code); removed rather than left in place looking load-bearing.
