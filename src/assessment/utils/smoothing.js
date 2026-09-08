/**
 * Signal smoothing and summary statistics.
 *
 * Pose estimation output is noisy frame to frame. A single frame must never be
 * able to become a measurement on its own, so every measured signal is passed
 * through a median filter before any peak or threshold logic sees it.
 */

/** Median of a numeric array. Returns null for an empty array. */
export function median(values) {
  const usable = values.filter((value) => Number.isFinite(value));

  if (!usable.length) return null;

  const sorted = [...usable].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);

  return sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle];
}

export function mean(values) {
  const usable = values.filter((value) => Number.isFinite(value));

  if (!usable.length) return null;

  return usable.reduce((sum, value) => sum + value, 0) / usable.length;
}

/**
 * Streaming median filter.
 *
 * A median is used rather than an average because pose estimation produces
 * occasional single-frame outliers, which an average would drag the signal
 * toward and a median discards.
 */
export class MedianFilter {
  constructor(windowSize) {
    this.windowSize = Math.max(1, windowSize | 0);
    this.buffer = [];
  }

  /** Push a sample and return the current filtered value. */
  push(value) {
    if (!Number.isFinite(value)) return this.value();

    this.buffer.push(value);

    if (this.buffer.length > this.windowSize) {
      this.buffer.shift();
    }

    return this.value();
  }

  /**
   * Current filtered value, or null until the window has filled. Refusing to
   * report a value early is deliberate: a half-full window is exactly where a
   * single noisy frame could dominate.
   */
  value() {
    if (this.buffer.length < this.windowSize) return null;

    return median(this.buffer);
  }

  /** Filtered value from however many samples exist, for end-of-run flushing. */
  partialValue() {
    return median(this.buffer);
  }

  reset() {
    this.buffer = [];
  }
}

/** Apply a median filter across a whole array, for offline/fixture use. */
export function medianFilterSeries(values, windowSize) {
  const filter = new MedianFilter(windowSize);

  return values.map((value) => filter.push(value));
}
