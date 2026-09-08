/**
 * Repetition detection on a smoothed one-dimensional signal.
 *
 * A two-threshold (hysteresis) scheme is used rather than local-maximum search
 * because a single threshold makes the detector chatter around the boundary and
 * count one movement several times. The signal must rise past `enterThreshold`
 * and then fall back past `exitThreshold` before another repetition can begin.
 *
 * Excursions shorter than `minDurationMs` are rejected as jitter; excursions
 * longer than `maxDurationMs` are rejected because the signal has almost
 * certainly drifted rather than the person having moved.
 */

export const REP_STATE = {
  BELOW: "below",
  ACTIVE: "active",
};

export const REP_EVENT = {
  NONE: null,
  ENTERED: "entered",
  COMPLETED: "completed",
  REJECTED: "rejected",
};

export class RepetitionDetector {
  /**
   * @param {object} options
   * @param {number} options.enterThreshold signal value that begins an excursion
   * @param {number} options.exitThreshold  value the signal must fall back to
   * @param {number} options.minDurationMs  shorter excursions are jitter
   * @param {number} options.maxDurationMs  longer excursions are signal drift
   * @param {number} [options.minSeparationMs] debounce between entered events
   */
  constructor({
    enterThreshold,
    exitThreshold,
    minDurationMs = 0,
    maxDurationMs = Infinity,
    minSeparationMs = 0,
  }) {
    if (!(enterThreshold > exitThreshold)) {
      throw new Error("enterThreshold must be greater than exitThreshold");
    }

    this.enterThreshold = enterThreshold;
    this.exitThreshold = exitThreshold;
    this.minDurationMs = minDurationMs;
    this.maxDurationMs = maxDurationMs;
    this.minSeparationMs = minSeparationMs;

    this.reset();
  }

  reset() {
    this.state = REP_STATE.BELOW;
    this.repetitions = [];
    this.rejected = [];
    this.current = null;
    this.lastEnteredAt = null;
  }

  /**
   * Feed one smoothed sample.
   *
   * @param {number|null} value smoothed signal, null while unavailable
   * @param {number} timestamp milliseconds
   * @returns {{state: string, event: string|null, repetition: object|null, reason: string|null}}
   */
  push(value, timestamp) {
    const idle = { state: this.state, event: REP_EVENT.NONE, repetition: null, reason: null };

    if (value === null || !Number.isFinite(value)) return idle;

    if (this.state === REP_STATE.BELOW) {
      if (value < this.enterThreshold) return idle;

      // Debounce: an immediate re-entry after the previous one is chatter.
      if (
        this.lastEnteredAt !== null &&
        timestamp - this.lastEnteredAt < this.minSeparationMs
      ) {
        return idle;
      }

      this.state = REP_STATE.ACTIVE;
      this.lastEnteredAt = timestamp;
      this.current = {
        startTimestamp: timestamp,
        peak: value,
        peakTimestamp: timestamp,
      };

      return {
        state: this.state,
        event: REP_EVENT.ENTERED,
        repetition: null,
        reason: null,
      };
    }

    // Active phase: track the highest smoothed value seen.
    if (value > this.current.peak) {
      this.current.peak = value;
      this.current.peakTimestamp = timestamp;
    }

    const elapsed = timestamp - this.current.startTimestamp;

    if (elapsed > this.maxDurationMs) {
      const reason = "too_slow";

      this.rejected.push({ ...this.current, endTimestamp: timestamp, durationMs: elapsed, reason });
      this.state = REP_STATE.BELOW;
      this.current = null;

      return { state: this.state, event: REP_EVENT.REJECTED, repetition: null, reason };
    }

    if (value > this.exitThreshold) {
      return { state: this.state, event: REP_EVENT.NONE, repetition: null, reason: null };
    }

    // Fell back below the exit threshold: the excursion is over.
    const repetition = {
      ...this.current,
      endTimestamp: timestamp,
      durationMs: elapsed,
    };

    this.state = REP_STATE.BELOW;
    this.current = null;

    if (elapsed < this.minDurationMs) {
      const reason = "too_fast";

      this.rejected.push({ ...repetition, reason });

      return { state: this.state, event: REP_EVENT.REJECTED, repetition: null, reason };
    }

    this.repetitions.push(repetition);

    return {
      state: this.state,
      event: REP_EVENT.COMPLETED,
      repetition,
      reason: null,
    };
  }

  /** Completed, accepted repetitions in order. */
  validRepetitions() {
    return this.repetitions;
  }

  /** Peak values of the accepted repetitions. */
  peaks() {
    return this.repetitions.map((repetition) => repetition.peak);
  }

  /** True while the signal is inside an excursion. */
  isActive() {
    return this.state === REP_STATE.ACTIVE;
  }
}

/**
 * Offline convenience wrapper: run a detector across a whole smoothed series.
 * Used by the fixture-driven unit tests.
 */
export function detectRepetitions(samples, options) {
  const detector = new RepetitionDetector(options);
  const events = [];

  samples.forEach(({ value, timestamp }) => {
    const result = detector.push(value, timestamp);

    if (result.event) events.push(result);
  });

  return {
    repetitions: detector.validRepetitions(),
    rejected: detector.rejected,
    peaks: detector.peaks(),
    events,
  };
}
