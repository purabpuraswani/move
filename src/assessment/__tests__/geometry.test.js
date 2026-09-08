/**
 * Geometry, smoothing, and repetition detection.
 * Run with: node --test src/assessment/__tests__/
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  angleBetween,
  distance,
  elevationFromDown,
  jointAngle,
  midpoint,
  round,
  shoulderTorsoRatio,
  tiltFromVertical,
} from "../utils/geometry.js";
import { median, mean, MedianFilter, medianFilterSeries } from "../utils/smoothing.js";
import { RepetitionDetector, detectRepetitions, REP_EVENT } from "../utils/peaks.js";

test("angleBetween returns null instead of NaN for a zero-length vector", () => {
  assert.equal(angleBetween({ x: 0, y: 0 }, { x: 0, y: 1 }), null);
});

test("angleBetween is clamped and never produces NaN for parallel vectors", () => {
  assert.equal(angleBetween({ x: 3, y: 4 }, { x: 6, y: 8 }), 0);
  assert.equal(angleBetween({ x: 3, y: 4 }, { x: -3, y: -4 }), 180);
});

test("elevationFromDown: 0 is arm at the side, 90 horizontal, 180 overhead", () => {
  const shoulder = { x: 100, y: 100 };

  assert.equal(round(elevationFromDown(shoulder, { x: 100, y: 220 }), 3), 0);
  assert.equal(round(elevationFromDown(shoulder, { x: 220, y: 100 }), 3), 90);
  assert.equal(round(elevationFromDown(shoulder, { x: -20, y: 100 }), 3), 90);
  assert.equal(round(elevationFromDown(shoulder, { x: 100, y: -20 }), 3), 180);
});

test("elevationFromDown is unsigned, so left and right read the same", () => {
  const shoulder = { x: 100, y: 100 };

  const outward = elevationFromDown(shoulder, { x: 100 + 60, y: 100 - 60 });
  const inward = elevationFromDown(shoulder, { x: 100 - 60, y: 100 - 60 });

  assert.equal(round(outward, 3), round(inward, 3));
  assert.equal(round(outward, 3), 135);
});

test("jointAngle measures the interior angle at the vertex", () => {
  // Straight leg: hip above the knee, ankle below it.
  assert.equal(round(jointAngle({ x: 0, y: -100 }, { x: 0, y: 0 }, { x: 0, y: 100 }), 3), 180);

  // Right angle: hip horizontally behind the knee, ankle below it.
  assert.equal(round(jointAngle({ x: 100, y: 0 }, { x: 0, y: 0 }, { x: 0, y: 100 }), 3), 90);
});

test("tiltFromVertical folds obtuse angles so lean is 0-90 either way", () => {
  assert.equal(round(tiltFromVertical({ x: 0, y: 0 }, { x: 0, y: 100 }), 3), 0);
  assert.equal(round(tiltFromVertical({ x: 100, y: 0 }, { x: 0, y: 100 }), 3), 45);
  assert.equal(round(tiltFromVertical({ x: -100, y: 0 }, { x: 0, y: 100 }), 3), 45);

  // Upside down still reports a small tilt, not 180.
  assert.equal(round(tiltFromVertical({ x: 0, y: 100 }, { x: 0, y: 0 }), 3), 0);
});

test("shoulderTorsoRatio drops as the torso rotates away from the camera", () => {
  const hips = { left: { x: 270, y: 340 }, right: { x: 370, y: 340 } };

  const front = shoulderTorsoRatio(
    { x: 240, y: 150 },
    { x: 400, y: 150 },
    hips.left,
    hips.right
  );

  const side = shoulderTorsoRatio(
    { x: 310, y: 150 },
    { x: 330, y: 150 },
    hips.left,
    hips.right
  );

  assert.ok(front > 0.7, `expected a wide front-facing ratio, got ${front}`);
  assert.ok(side < 0.2, `expected a narrow side-facing ratio, got ${side}`);
});

test("shoulderTorsoRatio returns null rather than dividing by zero", () => {
  const point = { x: 10, y: 10 };

  assert.equal(shoulderTorsoRatio(point, point, point, point), null);
});

test("midpoint, distance, and round behave predictably, round preserves null", () => {
  assert.deepEqual(midpoint({ x: 0, y: 0 }, { x: 10, y: 20 }), { x: 5, y: 10 });
  assert.equal(distance({ x: 0, y: 0 }, { x: 3, y: 4 }), 5);
  assert.equal(round(1.2345, 2), 1.23);
  assert.equal(round(null), null);
  assert.equal(round(undefined), null);
  assert.equal(round(Number.NaN), null);
  assert.equal(round(Infinity), null);
});

test("median and mean ignore non-finite values, and return null when empty", () => {
  assert.equal(median([3, 1, 2]), 2);
  assert.equal(median([4, 1, 3, 2]), 2.5);
  assert.equal(median([1, Number.NaN, 3]), 2);
  assert.equal(median([]), null);
  assert.equal(median([Number.NaN]), null);
  assert.equal(mean([1, 2, 3]), 2);
  assert.equal(mean([]), null);
});

test("MedianFilter reports nothing until its window has filled", () => {
  const filter = new MedianFilter(5);

  assert.equal(filter.push(10), null);
  assert.equal(filter.push(10), null);
  assert.equal(filter.push(10), null);
  assert.equal(filter.push(10), null);
  assert.equal(filter.push(10), 10);
});

test("a single-frame outlier cannot become the measurement", () => {
  const filter = new MedianFilter(5);
  const values = [10, 10, 900, 10, 10];

  let last = null;

  for (const value of values) last = filter.push(value);

  assert.equal(last, 10);
});

test("MedianFilter keeps its last value when handed a non-finite sample", () => {
  const filter = new MedianFilter(3);

  filter.push(5);
  filter.push(5);
  assert.equal(filter.push(5), 5);
  assert.equal(filter.push(null), 5);
  assert.equal(filter.push(Number.NaN), 5);
});

test("MedianFilter partialValue flushes a half-full window, reset empties it", () => {
  const filter = new MedianFilter(5);

  filter.push(2);
  filter.push(6);

  assert.equal(filter.value(), null);
  assert.equal(filter.partialValue(), 4);

  filter.reset();
  assert.equal(filter.partialValue(), null);
});

test("medianFilterSeries lags the signal rather than inventing early values", () => {
  const smoothed = medianFilterSeries([0, 0, 0, 10, 20, 30, 40], 3);

  assert.deepEqual(smoothed, [null, null, 0, 0, 10, 20, 30]);
});

test("RepetitionDetector refuses thresholds that would chatter", () => {
  assert.throws(
    () => new RepetitionDetector({ enterThreshold: 30, exitThreshold: 30 }),
    /enterThreshold must be greater than exitThreshold/
  );
  assert.throws(
    () => new RepetitionDetector({ enterThreshold: 10, exitThreshold: 30 }),
    /enterThreshold must be greater than exitThreshold/
  );
});

/** Build evenly spaced samples for the offline detector. */
function samples(values, stepMs = 100) {
  return values.map((value, index) => ({ value, timestamp: index * stepMs }));
}

test("hysteresis counts one repetition per excursion, not one per crossing", () => {
  // Deliberately noisy around the enter threshold of 55.
  const series = samples([
    0, 20, 50, 56, 54, 57, 53, 58, 80, 90, 80, 58, 40, 20, 0,
    20, 56, 54, 57, 85, 60, 40, 10, 0,
  ]);

  const { repetitions, peaks } = detectRepetitions(series, {
    enterThreshold: 55,
    exitThreshold: 30,
    minDurationMs: 0,
    maxDurationMs: 20000,
  });

  assert.equal(repetitions.length, 2);
  assert.deepEqual(peaks, [90, 85]);
});

test("excursions shorter than the minimum are rejected as jitter", () => {
  const series = [
    { value: 0, timestamp: 0 },
    { value: 60, timestamp: 100 },
    { value: 0, timestamp: 200 },
  ];

  const { repetitions, rejected } = detectRepetitions(series, {
    enterThreshold: 55,
    exitThreshold: 30,
    minDurationMs: 400,
    maxDurationMs: 12000,
  });

  assert.equal(repetitions.length, 0);
  assert.equal(rejected.length, 1);
  assert.equal(rejected[0].reason, "too_fast");
});

test("excursions longer than the maximum are rejected as signal drift", () => {
  const series = [
    { value: 0, timestamp: 0 },
    { value: 60, timestamp: 100 },
    { value: 60, timestamp: 5000 },
    { value: 0, timestamp: 5100 },
  ];

  const { repetitions, rejected, events } = detectRepetitions(series, {
    enterThreshold: 55,
    exitThreshold: 30,
    minDurationMs: 0,
    maxDurationMs: 1000,
  });

  assert.equal(repetitions.length, 0);
  assert.equal(rejected.length, 1);
  assert.equal(rejected[0].reason, "too_slow");
  assert.deepEqual(
    events.map((event) => event.event),
    [REP_EVENT.ENTERED, REP_EVENT.REJECTED]
  );
});

test("minSeparationMs debounces an immediate re-entry", () => {
  const series = [
    { value: 0, timestamp: 0 },
    { value: 60, timestamp: 100 },
    { value: 0, timestamp: 200 },
    { value: 60, timestamp: 300 },
    { value: 0, timestamp: 400 },
    { value: 60, timestamp: 700 },
    { value: 0, timestamp: 800 },
  ];

  const { repetitions } = detectRepetitions(series, {
    enterThreshold: 55,
    exitThreshold: 30,
    minDurationMs: 0,
    maxDurationMs: 12000,
    minSeparationMs: 500,
  });

  assert.equal(repetitions.length, 2);
  assert.deepEqual(
    repetitions.map((repetition) => repetition.startTimestamp),
    [100, 700]
  );
});

test("null samples are ignored so a filter warm-up cannot start a repetition", () => {
  const detector = new RepetitionDetector({
    enterThreshold: 55,
    exitThreshold: 30,
    minDurationMs: 0,
    maxDurationMs: 12000,
  });

  assert.equal(detector.push(null, 0).event, REP_EVENT.NONE);
  assert.equal(detector.push(Number.NaN, 100).event, REP_EVENT.NONE);
  assert.equal(detector.isActive(), false);

  assert.equal(detector.push(60, 200).event, REP_EVENT.ENTERED);
  assert.equal(detector.isActive(), true);
});

test("the peak of a repetition is the highest smoothed value inside it", () => {
  const detector = new RepetitionDetector({
    enterThreshold: 55,
    exitThreshold: 30,
    minDurationMs: 0,
    maxDurationMs: 12000,
  });

  [
    [0, 0],
    [60, 100],
    [120, 200],
    [148, 300],
    [120, 400],
    [10, 500],
  ].forEach(([value, timestamp]) => detector.push(value, timestamp));

  assert.deepEqual(detector.peaks(), [148]);
  assert.equal(detector.validRepetitions()[0].peakTimestamp, 300);
  assert.equal(detector.validRepetitions()[0].durationMs, 400);
});
