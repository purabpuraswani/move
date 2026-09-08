/**
 * A generic, exercise-agnostic hold-duration engine.
 *
 * The Exercise-Specific Movement Assessment foundation for any exercise
 * measured by "hold a valid position for as long as possible" — a wall sit,
 * a supported single-leg stand. Built the same way as RepCountingEngine:
 * a thin configuration layer over MedianFilter (src/assessment/utils/
 * smoothing.js), using the same hysteresis idea the baseline balance test
 * (src/assessment/tests/balance/balanceLogic.js) already relies on — a
 * position must be re-validated continuously, not sampled once — rather
 * than a new, separate timing algorithm.
 *
 * Same boundaries as RepCountingEngine: this module has no idea what a
 * keypoint is, calls no model, and its input/output are plain numbers.
 * Turning camera keypoints into "is the position currently valid" for any
 * specific exercise is separate, exercise-specific work.
 */

import { MedianFilter } from "../assessment/utils/smoothing.js";

export const HOLD_STATE = {
  INVALID: "invalid",
  STABILIZING: "stabilizing",
  HOLDING: "holding",
};

export class HoldDurationEngine {
  /**
   * @param {object} config
   * @param {number} config.validMin        lower bound of a valid smoothed value
   * @param {number} config.validMax        upper bound of a valid smoothed value
   * @param {number} [config.smoothingWindow]
   * @param {number} [config.stabilizationMs] how long a valid position must be
   *   held before timing starts, matching BALANCE.stabilizationMs's intent
   * @param {number} [config.maxDurationMs] a ceiling; reaching it is a valid
   *   complete result, not a failure (matching BALANCE.maxDurationMs's intent)
   */
  constructor({
    validMin,
    validMax,
    smoothingWindow = 5,
    stabilizationMs = 0,
    maxDurationMs = Infinity,
  }) {
    if (!(validMax >= validMin)) {
      throw new Error("validMax must be greater than or equal to validMin");
    }

    this.validMin = validMin;
    this.validMax = validMax;
    this.stabilizationMs = stabilizationMs;
    this.maxDurationMs = maxDurationMs;
    this.filter = new MedianFilter(smoothingWindow);

    this.state = HOLD_STATE.INVALID;
    this.validSinceTimestamp = null;
    this.holdStartTimestamp = null;
    this.durationMs = 0;
    this.reachedMaxDuration = false;
  }

  /** Feed one raw sample. Returns `{ state, durationMs }`. */
  push(rawValue, timestamp) {
    const smoothed = this.filter.push(rawValue);
    const valid =
      smoothed !== null && smoothed >= this.validMin && smoothed <= this.validMax;

    if (!valid) {
      this.state = HOLD_STATE.INVALID;
      this.validSinceTimestamp = null;
      this.holdStartTimestamp = null;

      return { state: this.state, durationMs: this.durationMs };
    }

    if (this.state === HOLD_STATE.INVALID) {
      this.state = HOLD_STATE.STABILIZING;
      this.validSinceTimestamp = timestamp;

      return { state: this.state, durationMs: this.durationMs };
    }

    if (this.state === HOLD_STATE.STABILIZING) {
      if (timestamp - this.validSinceTimestamp >= this.stabilizationMs) {
        this.state = HOLD_STATE.HOLDING;
        // Timing starts from when the position FIRST became valid, not from
        // this sample — otherwise every stabilization period would be lost
        // from the reported duration, understating how long the position
        // was actually held.
        this.holdStartTimestamp = this.validSinceTimestamp;
      } else {
        return { state: this.state, durationMs: this.durationMs };
      }
    }

    // HOLDING
    const elapsed = timestamp - this.holdStartTimestamp;
    this.durationMs = Math.min(elapsed, this.maxDurationMs);
    this.reachedMaxDuration = this.durationMs >= this.maxDurationMs;

    return { state: this.state, durationMs: this.durationMs };
  }

  /**
   * A structured, privacy-safe summary suitable for
   * backend/exercise_assessment/schema.py's `measurements`
   * (durationSeconds, completion) — never raw signal history.
   */
  summary() {
    const durationSeconds = Math.round((this.durationMs / 1000) * 100) / 100;
    const completion = Number.isFinite(this.maxDurationMs)
      ? Math.min(1, this.durationMs / this.maxDurationMs)
      : null;

    return { durationSeconds, completion };
  }

  reset() {
    this.filter.reset();
    this.state = HOLD_STATE.INVALID;
    this.validSinceTimestamp = null;
    this.holdStartTimestamp = null;
    this.durationMs = 0;
    this.reachedMaxDuration = false;
  }
}
