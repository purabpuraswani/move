/**
 * A generic, exercise-agnostic repetition-counting engine.
 *
 * This is the Exercise-Specific Movement Assessment foundation for any
 * exercise measured by "a single numeric signal crosses a threshold and
 * comes back, N times" — a knee lift angle, a calf-raise heel angle, a
 * side-leg-raise angle, a hip-extension angle, a push-up elbow-bend angle,
 * a sit-to-stand transition angle. It does not re-implement repetition
 * detection: it is a thin, documented configuration layer over
 * RepetitionDetector (src/assessment/utils/peaks.js) and MedianFilter
 * (src/assessment/utils/smoothing.js), the same primitives the three
 * baseline tests already use — extended to a new exercise, never
 * duplicated for one.
 *
 * What this module explicitly does NOT do:
 *   - It does not know how to turn camera keypoints into an angle for any
 *     specific exercise. That per-exercise "keypoints -> one number" step
 *     (the equivalent of shoulderLogic.js's angle calculation) is separate,
 *     exercise-specific work for whichever phase wires a live camera loop
 *     to a given exercise — this engine only consumes the resulting number.
 *   - It never touches a keypoint, a frame, or an image. Its entire input
 *     is `{ value: number|null, timestamp: number }` — a single already-
 *     derived measurement per sample — and its entire output is plain
 *     numbers (counts, durations). Nothing it produces or consumes could
 *     be mistaken for pose data.
 *   - It is not an LLM and calls no model. It is deterministic threshold
 *     logic, identical in kind to RepetitionDetector.
 */

import { RepetitionDetector } from "../assessment/utils/peaks.js";
import { MedianFilter } from "../assessment/utils/smoothing.js";

export class RepCountingEngine {
  /**
   * @param {object} config
   * @param {number} config.enterThreshold  signal value that begins a repetition
   * @param {number} config.exitThreshold   value the signal must fall back to
   * @param {number} [config.smoothingWindow] median filter window, in samples
   * @param {number} [config.minDurationMs]
   * @param {number} [config.maxDurationMs]
   * @param {number} [config.targetRepetitions] how many reps count as "complete"
   */
  constructor({
    enterThreshold,
    exitThreshold,
    smoothingWindow = 5,
    minDurationMs = 0,
    maxDurationMs = Infinity,
    targetRepetitions = null,
  }) {
    this.targetRepetitions = targetRepetitions;
    this.filter = new MedianFilter(smoothingWindow);
    this.detector = new RepetitionDetector({
      enterThreshold,
      exitThreshold,
      minDurationMs,
      maxDurationMs,
    });
  }

  /**
   * Feed one raw sample (already derived from a pose — never a keypoint or
   * frame itself). Returns the detector's event for this sample.
   */
  push(rawValue, timestamp) {
    const smoothed = this.filter.push(rawValue);

    return this.detector.push(smoothed, timestamp);
  }

  /** Accepted repetition count so far. */
  repetitionCount() {
    return this.detector.validRepetitions().length;
  }

  /** Whether the target repetition count (if one was configured) is met. */
  hasEnoughRepetitions() {
    if (this.targetRepetitions === null) return false;

    return this.repetitionCount() >= this.targetRepetitions;
  }

  /**
   * A structured, privacy-safe summary suitable for
   * backend/exercise_assessment/schema.py's `measurements` (repetitions,
   * durationSeconds, completion) — never raw signal history. durationSeconds
   * is the span from the first repetition's start to the last repetition's
   * end (null until at least one repetition has completed), not a running
   * session clock.
   */
  summary() {
    const accepted = this.detector.validRepetitions();
    const repetitions = accepted.length;
    const completion =
      this.targetRepetitions === null
        ? null
        : Math.min(1, repetitions / this.targetRepetitions);
    const durationSeconds = accepted.length
      ? Math.round(
          ((accepted[accepted.length - 1].endTimestamp - accepted[0].startTimestamp) / 1000) * 100
        ) / 100
      : null;

    return { repetitions, completion, durationSeconds };
  }

  reset() {
    this.filter.reset();
    this.detector.reset();
  }
}
