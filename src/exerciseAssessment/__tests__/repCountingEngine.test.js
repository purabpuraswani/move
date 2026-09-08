import test from "node:test";
import assert from "node:assert/strict";

import { RepCountingEngine } from "../repCountingEngine.js";

function feed(engine, samples) {
  return samples.map(({ value, timestamp }) => engine.push(value, timestamp));
}

test("counts a clean repetition once it rises past enter and falls past exit", () => {
  const engine = new RepCountingEngine({
    enterThreshold: 50,
    exitThreshold: 20,
    smoothingWindow: 1,
    minDurationMs: 100,
    targetRepetitions: 1,
  });

  feed(engine, [
    { value: 0, timestamp: 0 },
    { value: 60, timestamp: 200 },
    { value: 65, timestamp: 400 },
    { value: 10, timestamp: 700 },
  ]);

  assert.equal(engine.repetitionCount(), 1);
  assert.equal(engine.hasEnoughRepetitions(), true);
});

test("does not count a repetition that never falls back below exit", () => {
  const engine = new RepCountingEngine({
    enterThreshold: 50,
    exitThreshold: 20,
    smoothingWindow: 1,
    targetRepetitions: 1,
  });

  feed(engine, [
    { value: 0, timestamp: 0 },
    { value: 60, timestamp: 200 },
    { value: 55, timestamp: 400 },
  ]);

  assert.equal(engine.repetitionCount(), 0);
  assert.equal(engine.hasEnoughRepetitions(), false);
});

test("rejects an excursion shorter than minDurationMs as jitter", () => {
  const engine = new RepCountingEngine({
    enterThreshold: 50,
    exitThreshold: 20,
    smoothingWindow: 1,
    minDurationMs: 500,
    targetRepetitions: 1,
  });

  feed(engine, [
    { value: 0, timestamp: 0 },
    { value: 60, timestamp: 10 },
    { value: 10, timestamp: 20 },
  ]);

  assert.equal(engine.repetitionCount(), 0);
});

test("ten repetitions reach a target of ten with completion 1", () => {
  const engine = new RepCountingEngine({
    enterThreshold: 50,
    exitThreshold: 20,
    smoothingWindow: 1,
    minDurationMs: 100,
    targetRepetitions: 10,
  });

  let t = 0;
  for (let i = 0; i < 10; i += 1) {
    feed(engine, [
      { value: 0, timestamp: t },
      { value: 60, timestamp: t + 200 },
      { value: 10, timestamp: t + 500 },
    ]);
    t += 700;
  }

  assert.equal(engine.repetitionCount(), 10);
  assert.equal(engine.hasEnoughRepetitions(), true);
  assert.equal(engine.summary().completion, 1);
});

test("summary reports null completion with no configured target", () => {
  const engine = new RepCountingEngine({ enterThreshold: 50, exitThreshold: 20, smoothingWindow: 1 });
  assert.equal(engine.summary().completion, null);
});

test("summary reports null durationSeconds before any repetition completes", () => {
  const engine = new RepCountingEngine({ enterThreshold: 50, exitThreshold: 20, smoothingWindow: 1 });
  assert.equal(engine.summary().durationSeconds, null);
});

test("summary reports a positive durationSeconds spanning first-to-last repetition", () => {
  const engine = new RepCountingEngine({
    enterThreshold: 50,
    exitThreshold: 20,
    smoothingWindow: 1,
    minDurationMs: 100,
    targetRepetitions: 2,
  });

  feed(engine, [
    { value: 0, timestamp: 0 },
    { value: 60, timestamp: 200 },
    { value: 10, timestamp: 500 },
    { value: 60, timestamp: 1200 },
    { value: 10, timestamp: 1500 },
  ]);

  const summary = engine.summary();
  assert.equal(summary.repetitions, 2);
  assert.equal(summary.durationSeconds, 1.3);
});

test("null and non-finite samples do not crash the engine", () => {
  const engine = new RepCountingEngine({ enterThreshold: 50, exitThreshold: 20, smoothingWindow: 1 });
  assert.doesNotThrow(() => {
    engine.push(null, 0);
    engine.push(NaN, 100);
    engine.push(undefined, 200);
  });
  assert.equal(engine.repetitionCount(), 0);
});

test("reset clears repetition count and filter state", () => {
  const engine = new RepCountingEngine({
    enterThreshold: 50,
    exitThreshold: 20,
    smoothingWindow: 1,
    minDurationMs: 100,
    targetRepetitions: 1,
  });

  feed(engine, [
    { value: 0, timestamp: 0 },
    { value: 60, timestamp: 200 },
    { value: 10, timestamp: 500 },
  ]);
  assert.equal(engine.repetitionCount(), 1);

  engine.reset();
  assert.equal(engine.repetitionCount(), 0);
});

test("never sees or produces anything resembling a keypoint or frame", () => {
  const engine = new RepCountingEngine({ enterThreshold: 50, exitThreshold: 20, smoothingWindow: 1 });
  const result = engine.push(42, 0);
  const allKeys = JSON.stringify({ result, summary: engine.summary() }).toLowerCase();
  for (const forbidden of ["keypoint", "landmark", "pose", "frame", "image", "video"]) {
    assert.ok(!allKeys.includes(forbidden), `unexpected "${forbidden}" in engine output`);
  }
});
