/**
 * The arithmetic behind the progress line charts.
 *
 * Kept separate from the component so it can be tested directly: this
 * project runs `node --test` over plain JS and has no React render
 * infrastructure, so geometry that lives inside a component is geometry
 * that cannot be tested. Everything here is pure.
 *
 * The charts draw in a fixed viewBox and are scaled by CSS, which is
 * what makes them responsive without measuring the DOM.
 */

export const VIEWBOX_WIDTH = 640;
export const VIEWBOX_HEIGHT = 220;
export const PADDING = { top: 16, right: 16, bottom: 32, left: 44 };

/** A series needs at least this many points before a line means anything. */
export const MIN_POINTS_FOR_TREND = 2;

/**
 * The value range to draw, padded so a flat line is not drawn on the axis
 * and a single repeated value still renders sensibly.
 */
export function valueRange(values) {
  const numbers = (values || []).filter((value) => Number.isFinite(value));

  if (!numbers.length) return null;

  let min = Math.min(...numbers);
  let max = Math.max(...numbers);

  if (min === max) {
    // A flat series is real data, not an error: give it a band to sit in
    // so the line appears mid-chart rather than clipped to an edge.
    const band = Math.abs(min) > 0 ? Math.abs(min) * 0.1 : 1;

    min -= band;
    max += band;
  }

  return { min, max };
}

/** Pixel positions for each point, left to right in array order. */
export function plotPoints(values, { width = VIEWBOX_WIDTH, height = VIEWBOX_HEIGHT } = {}) {
  const numbers = (values || []).filter((value) => Number.isFinite(value));
  const range = valueRange(numbers);

  if (!range || numbers.length === 0) return [];

  const innerWidth = width - PADDING.left - PADDING.right;
  const innerHeight = height - PADDING.top - PADDING.bottom;
  const span = range.max - range.min;

  return numbers.map((value, index) => {
    // A single point sits in the middle rather than at x=0, where it
    // would be half outside the plot area.
    const ratio = numbers.length === 1 ? 0.5 : index / (numbers.length - 1);

    return {
      x: PADDING.left + ratio * innerWidth,
      // SVG y grows downward, so a bigger value must sit higher.
      y: PADDING.top + (1 - (value - range.min) / span) * innerHeight,
      value,
    };
  });
}

/** An SVG path through the points, or "" when there is nothing to draw. */
export function linePath(values, options) {
  const points = plotPoints(values, options);

  if (points.length < MIN_POINTS_FOR_TREND) return "";

  return points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");
}

/**
 * Whether this series may be drawn as a trend.
 *
 * Honours the backend's own `plottable` flag when one is present, so the
 * threshold is decided in a single place; falls back to counting only
 * when the flag is absent.
 */
export function isPlottable(series) {
  if (!series) return false;

  if (typeof series.plottable === "boolean") return series.plottable;

  return (series.points || []).length >= MIN_POINTS_FOR_TREND;
}

/** Axis labels: the first and last point's date, plus min/max values. */
export function axisLabels(series) {
  const points = (series && series.points) || [];

  if (!points.length) return null;

  const values = points
    .map((point) => (typeof point.value === "number" ? point.value : point.total))
    .filter((value) => Number.isFinite(value));

  const range = valueRange(values);

  if (!range) return null;

  return {
    firstDate: points[0].date || null,
    lastDate: points[points.length - 1].date || null,
    min: Math.min(...values),
    max: Math.max(...values),
  };
}
