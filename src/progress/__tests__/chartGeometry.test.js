/**
 * The progress charts' arithmetic, and the line they must not cross.
 *
 * The guarantee worth testing is negative: a series with one recorded
 * point must never produce a drawable line. A chart that draws a trend
 * through a single dot is a chart that invents one.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  MIN_POINTS_FOR_TREND,
  PADDING,
  VIEWBOX_HEIGHT,
  VIEWBOX_WIDTH,
  axisLabels,
  isPlottable,
  linePath,
  plotPoints,
  valueRange,
} from "../chartGeometry.js";

test("a single point produces no path at all", () => {
  assert.equal(linePath([5]), "");
});

test("an empty series produces no path", () => {
  assert.equal(linePath([]), "");
  assert.equal(linePath(undefined), "");
});

test("two points produce a line with both of them", () => {
  const path = linePath([3, 9]);

  assert.match(path, /^M/);
  assert.equal(path.split("L").length, 2);
});

test("a higher value is drawn higher on the chart", () => {
  // SVG y grows downward, so the larger value must have the smaller y.
  const [low, high] = plotPoints([10, 90]);

  assert.ok(high.y < low.y, "the larger value was not drawn above the smaller");
});

test("points stay inside the plot area", () => {
  for (const point of plotPoints([1, 50, 100, 2])) {
    assert.ok(point.x >= PADDING.left);
    assert.ok(point.x <= VIEWBOX_WIDTH - PADDING.right);
    assert.ok(point.y >= PADDING.top);
    assert.ok(point.y <= VIEWBOX_HEIGHT - PADDING.bottom);
  }
});

test("points are spaced left to right in series order", () => {
  const xs = plotPoints([4, 5, 6, 7]).map((point) => point.x);

  assert.deepEqual(xs, [...xs].sort((a, b) => a - b));
});

test("a flat series is drawn as a flat line, not a divide-by-zero", () => {
  const points = plotPoints([20, 20, 20]);

  for (const point of points) {
    assert.ok(Number.isFinite(point.y), "a flat series produced a non-finite y");
  }

  assert.equal(new Set(points.map((point) => point.y.toFixed(4))).size, 1);
});

test("a single point sits in the middle rather than on the edge", () => {
  const [only] = plotPoints([42]);

  assert.ok(only.x > PADDING.left);
  assert.ok(only.x < VIEWBOX_WIDTH - PADDING.right);
});

test("valueRange reports null when there is nothing to scale", () => {
  assert.equal(valueRange([]), null);
  assert.equal(valueRange([null, undefined, NaN]), null);
});

test("non-numeric values are ignored rather than plotted as zero", () => {
  // A missing measurement must not become a point at the bottom of the
  // chart, which would read as a collapse that never happened.
  assert.equal(plotPoints([10, null, 20]).length, 2);
});

test("isPlottable honours the backend flag over its own counting", () => {
  // The threshold lives in progress_agent/series.py. If the backend says
  // a two-point series is not plottable, the chart must believe it.
  assert.equal(isPlottable({ plottable: false, points: [{}, {}, {}] }), false);
  assert.equal(isPlottable({ plottable: true, points: [{}, {}] }), true);
});

test("isPlottable falls back to the shared threshold when no flag is sent", () => {
  assert.equal(isPlottable({ points: [{}] }), false);
  assert.equal(isPlottable({ points: new Array(MIN_POINTS_FOR_TREND).fill({}) }), true);
  assert.equal(isPlottable(null), false);
});

test("axisLabels reports the real first and last dates and the real range", () => {
  const labels = axisLabels({
    points: [
      { date: "2026-08-01", value: 12 },
      { date: "2026-09-01", value: 18 },
    ],
  });

  assert.equal(labels.firstDate, "2026-08-01");
  assert.equal(labels.lastDate, "2026-09-01");
  assert.equal(labels.min, 12);
  assert.equal(labels.max, 18);
});

test("axisLabels reads the completions series' own count field", () => {
  // The completions series carries `total` rather than `value`; the
  // labels must not silently report nothing for it.
  const labels = axisLabels({
    points: [
      { date: "2026-08-01", total: 2 },
      { date: "2026-08-02", total: 5 },
    ],
  });

  assert.equal(labels.min, 2);
  assert.equal(labels.max, 5);
});
