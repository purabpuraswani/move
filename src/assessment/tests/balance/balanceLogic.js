/**
 * Test 3 - eyes-open single-leg stance. Front-facing camera.
 *
 * WHAT IS MEASURED
 * How long the person keeps one foot visibly lifted while remaining within
 * observable position limits, measured separately for each support leg.
 *
 * WHAT IS NOT MEASURED
 * This is not a measure of balance ability, vestibular function, neurological
 * status, or fall risk. Loss of position is detected from what the camera can
 * see; a person may also stop simply because they chose to. The user is told
 * throughout that they should only attempt this if they feel safe, and skipping
 * is always allowed.
 *
 * One instance of this class measures ONE support leg. The page runs it twice
 * and combines the two with combineBalanceResults.
 */

import { BALANCE, POSE, REASON, SHOULDER } from "../../config/protocol.js";
import { distance, midpoint, tiltFromVertical, round } from "../../utils/geometry.js";
import { MedianFilter } from "../../utils/smoothing.js";
import { measuredResult, skippedResult } from "../../utils/results.js";
import { SIDE_KEYPOINTS, otherSide } from "../../utils/keypoints.js";
import {
  REQUIRED_KEYPOINTS,
  QualityTracker,
  checkRequiredKeypoints,
  checkFrontFacing,
  combineChecks,
} from "../../utils/validation.js";

export const BALANCE_PHASE = {
  WAITING: "waiting",
  STABILISING: "stabilising",
  TIMING: "timing",
  DONE: "done",
};

export const END_REASON = {
  FOOT_LOWERED: REASON.FOOT_LOWERED,
  TRUNK_LEAN: REASON.EXCESSIVE_TRUNK_LEAN,
  SUPPORT_FOOT_MOVED: REASON.SUPPORT_FOOT_MOVED,
  POSE_LOST: REASON.POSE_LOST,
  MAX_DURATION: REASON.MAX_DURATION_REACHED,
  ABORTED: REASON.ABORTED_BY_USER,
  NEVER_STARTED: REASON.NO_VALID_POSITION,
};

export class SingleLegStanceTest {
  /**
   * @param {object} options
   * @param {"left"|"right"} options.supportSide the leg being stood on
   * @param {object} [options.config]
   */
  constructor({ supportSide, config = BALANCE }) {
    if (supportSide !== "left" && supportSide !== "right") {
      throw new Error(`supportSide must be "left" or "right", got ${supportSide}`);
    }

    this.supportSide = supportSide;
    this.liftedSide = otherSide(supportSide);
    this.config = config;
    this.reset();
  }

  reset() {
    this.phase = BALANCE_PHASE.WAITING;

    this.quality = new QualityTracker({
      trackedKeypoints: REQUIRED_KEYPOINTS.balance,
    });

    this.filter = new MedianFilter(this.config.smoothingWindow);

    this.liftRatio = null;
    this.validPositionSince = null;
    this.lastTimestamp = null;
    this.startTimestamp = null;
    this.endTimestamp = null;
    this.durationMs = null;
    this.endReason = null;
    this.supportAnkleReferenceX = null;
    this.lastReasons = [];

    // Bounds the WAITING/STABILISING setup period so it cannot run forever;
    // see push() and #handleNotYetTiming().
    this.setupStartTimestamp = null;
  }

  push(frame) {
    this.lastTimestamp = frame.timestamp;

    if (this.phase === BALANCE_PHASE.DONE) return this.#status(true, []);

    if (this.setupStartTimestamp === null) this.setupStartTimestamp = frame.timestamp;

    // WAITING/STABILISING had no time limit: a slow or wobbly setup could run
    // indefinitely, feeding an unbounded number of frames into the quality
    // accounting before a hold was ever timed. Bound it explicitly and end
    // the attempt with the same reason used when a valid position is never
    // reached at all, rather than let it run forever.
    if (
      (this.phase === BALANCE_PHASE.WAITING || this.phase === BALANCE_PHASE.STABILISING) &&
      frame.timestamp - this.setupStartTimestamp >= this.config.maxSetupDurationMs
    ) {
      this.#end(frame.timestamp, END_REASON.NEVER_STARTED);

      return this.#status(true, []);
    }

    const keypointCheck = checkRequiredKeypoints(frame, REQUIRED_KEYPOINTS.balance);

    if (!keypointCheck.usable) {
      const state = this.#recordUnusable(frame, keypointCheck.reasons);

      // While timing, a long gap in usable pose means the end of the hold
      // cannot be located, so the attempt is ended and marked unreliable
      // rather than reporting a duration that might be wrong.
      if (this.phase === BALANCE_PHASE.TIMING && state.poseLostFor > POSE.maxPoseLossMs) {
        this.#end(frame.timestamp, END_REASON.POSE_LOST);
      } else if (this.phase === BALANCE_PHASE.STABILISING) {
        this.validPositionSince = null;
        this.phase = BALANCE_PHASE.WAITING;
      }

      return state;
    }

    const points = keypointCheck.points;

    const orientation = checkFrontFacing(points, SHOULDER.minFrontFacingRatio);
    const combined = combineChecks(orientation);

    if (!combined.usable) {
      return this.#recordUnusable(frame, combined.reasons);
    }

    this.quality.record(frame, true, []);

    const support = SIDE_KEYPOINTS[this.supportSide];
    const lifted = SIDE_KEYPOINTS[this.liftedSide];

    const supportAnkle = points[support.ankle];
    const liftedAnkle = points[lifted.ankle];
    const midHip = midpoint(points.left_hip, points.right_hip);

    // Body scale, so the lift threshold does not depend on camera distance.
    const scale = distance(midHip, supportAnkle);

    if (scale === 0) {
      return this.#recordUnusable(frame, [REASON.KEYPOINTS_MISSING]);
    }

    // y increases downward, so a lifted foot sits at a smaller y than the
    // support foot and produces a positive ratio.
    const rawRatio = (supportAnkle.y - liftedAnkle.y) / scale;
    const smoothed = this.filter.push(rawRatio);

    if (smoothed === null) return this.#status(true, []);

    this.liftRatio = smoothed;

    const trunkLean = tiltFromVertical(
      midpoint(points.left_shoulder, points.right_shoulder),
      midHip
    );

    if (this.phase === BALANCE_PHASE.WAITING || this.phase === BALANCE_PHASE.STABILISING) {
      this.#handleNotYetTiming(frame, smoothed, supportAnkle);

      return this.#status(true, []);
    }

    // Timing.
    if (smoothed < this.config.lossLiftRatio) {
      this.#end(frame.timestamp, END_REASON.FOOT_LOWERED);

      return this.#status(true, []);
    }

    if (trunkLean !== null && trunkLean > this.config.maxTrunkLeanDeg) {
      this.#end(frame.timestamp, END_REASON.TRUNK_LEAN);

      return this.#status(true, []);
    }

    const ankleShift = Math.abs(supportAnkle.x - this.supportAnkleReferenceX) / scale;

    if (ankleShift > this.config.maxSupportAnkleShiftRatio) {
      this.#end(frame.timestamp, END_REASON.SUPPORT_FOOT_MOVED);

      return this.#status(true, []);
    }

    if (frame.timestamp - this.startTimestamp >= this.config.maxDurationMs) {
      this.#end(frame.timestamp, END_REASON.MAX_DURATION);

      return this.#status(true, []);
    }

    return this.#status(true, []);
  }

  #handleNotYetTiming(frame, liftRatio, supportAnkle) {
    if (liftRatio < this.config.minLiftRatio) {
      this.validPositionSince = null;
      this.phase = BALANCE_PHASE.WAITING;

      return;
    }

    if (this.validPositionSince === null) {
      this.validPositionSince = frame.timestamp;
      this.phase = BALANCE_PHASE.STABILISING;

      return;
    }

    if (frame.timestamp - this.validPositionSince >= this.config.stabilizationMs) {
      this.phase = BALANCE_PHASE.TIMING;
      this.startTimestamp = frame.timestamp;
      this.supportAnkleReferenceX = supportAnkle.x;

      // The usable-frame check in finish() must judge the timed hold, not
      // the setup period that preceded it: a wobbly-but-bounded search for a
      // valid position should not by itself fail an otherwise clean hold.
      // Restarting the tracker here scopes quality.summary() and
      // blockingReasons() to the TIMING segment only.
      this.quality.reset();
    }
  }

  #end(timestamp, reason) {
    this.phase = BALANCE_PHASE.DONE;
    this.endTimestamp = timestamp;
    this.endReason = reason;
    this.durationMs = this.startTimestamp === null ? null : timestamp - this.startTimestamp;
  }

  #recordUnusable(frame, reasons) {
    const { poseLostFor } = this.quality.record(frame, false, reasons);

    this.lastReasons = reasons;

    return {
      phase: this.phase,
      usable: false,
      reasons,
      supportSide: this.supportSide,
      liftRatio: this.liftRatio,
      elapsedMs: this.elapsedMs(),
      poseLostFor,
    };
  }

  #status(usable, reasons) {
    this.lastReasons = reasons;

    return {
      phase: this.phase,
      usable,
      reasons,
      supportSide: this.supportSide,
      liftRatio: this.liftRatio,
      elapsedMs: this.elapsedMs(),
      poseLostFor: 0,
    };
  }

  /**
   * Time held so far, for live display. Once the hold has ended this is the
   * measured duration; while it is running it is the time up to the most recent
   * frame, so it is derived from frame timestamps rather than wall-clock time.
   */
  elapsedMs() {
    if (this.startTimestamp === null) return 0;

    if (this.durationMs !== null) return this.durationMs;

    const latest = this.endTimestamp ?? this.lastTimestamp ?? this.startTimestamp;

    return Math.max(0, latest - this.startTimestamp);
  }

  isDone() {
    return this.phase === BALANCE_PHASE.DONE;
  }

  /** Manual stop, e.g. the user pressed stop or stepped down deliberately. */
  stop(timestamp, reason = END_REASON.ABORTED) {
    if (this.phase !== BALANCE_PHASE.DONE) this.#end(timestamp, reason);
  }

  /**
   * Per-side result.
   *
   * A hold that ended because the position was lost is a complete, valid
   * measurement: the duration is the thing being measured. Only a run that
   * never achieved a valid position, or whose end could not be located because
   * the pose was lost, is invalid.
   */
  finish({ attempts = 1 } = {}) {
    if (this.phase !== BALANCE_PHASE.DONE) {
      this.#end(this.endTimestamp ?? this.startTimestamp ?? 0, this.startTimestamp === null
        ? END_REASON.NEVER_STARTED
        : END_REASON.ABORTED);
    }

    const invalidReasons = [...this.quality.blockingReasons()];

    if (this.startTimestamp === null) {
      if (!invalidReasons.includes(REASON.NO_VALID_POSITION)) {
        invalidReasons.push(REASON.NO_VALID_POSITION);
      }
    }

    if (this.endReason === END_REASON.POSE_LOST && !invalidReasons.includes(REASON.POSE_LOST)) {
      invalidReasons.push(REASON.POSE_LOST);
    }

    if (this.endReason === END_REASON.ABORTED) {
      invalidReasons.push(REASON.ABORTED_BY_USER);
    }

    const valid = invalidReasons.length === 0 && this.durationMs !== null;

    return {
      supportSide: this.supportSide,
      valid,
      holdDurationMs: valid ? Math.round(this.durationMs) : null,
      holdDurationSeconds: valid ? round(this.durationMs / 1000, 2) : null,
      reachedMaxDuration: this.endReason === END_REASON.MAX_DURATION,
      endReason: this.endReason,
      invalidReasons,
      quality: this.quality.summary(),
      attempts,
    };
  }
}

/** A side the user chose not to attempt. Duration stays null, never zero. */
export function skippedSide(supportSide) {
  return {
    supportSide,
    valid: false,
    skipped: true,
    holdDurationMs: null,
    holdDurationSeconds: null,
    reachedMaxDuration: false,
    endReason: null,
    invalidReasons: [],
    quality: null,
    attempts: 0,
  };
}

/**
 * Combine the two support legs into the single "balance" test result.
 *
 * The combined status is completed only when neither attempted side is invalid.
 * A usable measurement from one side is still kept and still carries its own
 * per-side validity, so nothing is thrown away, but the test as a whole is not
 * reported as completed while part of it failed.
 */
export function combineBalanceResults(left, right, { attempts = 1 } = {}) {
  const sides = [left, right];
  const attempted = sides.filter((side) => !side.skipped);

  if (!attempted.length) {
    return skippedResult("balance", { attempts });
  }

  const invalidReasons = [];

  for (const side of attempted) {
    for (const reason of side.invalidReasons) {
      const code = `${side.supportSide}:${reason}`;

      if (!invalidReasons.includes(code)) invalidReasons.push(code);
    }
  }

  const measurements = {
    left: {
      attempted: !left.skipped,
      valid: left.valid,
      holdDurationMs: left.holdDurationMs,
      holdDurationSeconds: left.holdDurationSeconds,
      reachedMaxDuration: left.reachedMaxDuration,
      endReason: left.endReason,
    },
    right: {
      attempted: !right.skipped,
      valid: right.valid,
      holdDurationMs: right.holdDurationMs,
      holdDurationSeconds: right.holdDurationSeconds,
      reachedMaxDuration: right.reachedMaxDuration,
      endReason: right.endReason,
    },
    observableDifferenceMs:
      left.valid && right.valid
        ? Math.abs(left.holdDurationMs - right.holdDurationMs)
        : null,
    maxDurationMs: BALANCE.maxDurationMs,
    definition: {
      quantity: "observable_single_leg_hold_duration",
      unit: "milliseconds",
      condition: "eyes_open",
      startsOn: "valid_lifted_position_held_for_stabilisation_window",
      endsOn: "observable_position_loss_or_maximum_duration",
      plane: "camera_image_plane_projection",
    },
  };

  return {
    ...measuredResult("balance", {
      valid: invalidReasons.length === 0,
      measurements,
      quality: {
        left: left.quality,
        right: right.quality,
      },
      invalidReasons,
      attempts,
    }),
  };
}
