import test from "node:test";
import assert from "node:assert/strict";

import { HoldDurationEngine, HOLD_STATE } from "../holdDurationEngine.js";

test("stays invalid while the signal is outside the valid range", () => {
  const engine = new HoldDurationEngine({ validMin: 0.1, validMax: 1, smoothingWindow: 1 });
  const result = engine.push(0.0, 0);
  assert.equal(result.state, HOLD_STATE.INVALID);
});

test("moves to stabilizing once valid, then holding after stabilizationMs", () => {
  const engine = new HoldDurationEngine({
    validMin: 0.1,
    validMax: 1,
    smoothingWindow: 1,
    stabilizationMs: 400,
  });

  let result = engine.push(0.5, 0);
  assert.equal(result.state, HOLD_STATE.STABILIZING);

  result = engine.push(0.5, 200);
  assert.equal(result.state, HOLD_STATE.STABILIZING);

  result = engine.push(0.5, 500);
  assert.equal(result.state, HOLD_STATE.HOLDING);
});

test("accumulates duration while holding", () => {
  const engine = new HoldDurationEngine({
    validMin: 0.1,
    validMax: 1,
    smoothingWindow: 1,
    stabilizationMs: 0,
  });

  engine.push(0.5, 0);
  engine.push(0.5, 1000);
  const result = engine.push(0.5, 3000);

  assert.equal(result.state, HOLD_STATE.HOLDING);
  assert.equal(result.durationMs, 3000);
});

test("dropping out of the valid range resets to invalid and stops accumulating", () => {
  const engine = new HoldDurationEngine({
    validMin: 0.1,
    validMax: 1,
    smoothingWindow: 1,
    stabilizationMs: 0,
  });

  engine.push(0.5, 0);
  engine.push(0.5, 2000);
  const dropped = engine.push(0.0, 2100);
  assert.equal(dropped.state, HOLD_STATE.INVALID);

  // Re-entering starts a fresh stabilization, not a resumed hold.
  const reentered = engine.push(0.5, 2200);
  assert.equal(reentered.state, HOLD_STATE.STABILIZING);
});

test("duration never exceeds maxDurationMs — reaching the ceiling is a valid complete result", () => {
  const engine = new HoldDurationEngine({
    validMin: 0.1,
    validMax: 1,
    smoothingWindow: 1,
    stabilizationMs: 0,
    maxDurationMs: 5000,
  });

  engine.push(0.5, 0);
  const result = engine.push(0.5, 20000);

  assert.equal(result.durationMs, 5000);
  assert.equal(engine.reachedMaxDuration, true);
});

test("summary reports durationSeconds and completion against maxDurationMs", () => {
  const engine = new HoldDurationEngine({
    validMin: 0.1,
    validMax: 1,
    smoothingWindow: 1,
    stabilizationMs: 0,
    maxDurationMs: 10000,
  });

  engine.push(0.5, 0);
  engine.push(0.5, 5000);

  const summary = engine.summary();
  assert.equal(summary.durationSeconds, 5);
  assert.equal(summary.completion, 0.5);
});

test("summary completion is null when no maxDurationMs is configured", () => {
  const engine = new HoldDurationEngine({ validMin: 0.1, validMax: 1, smoothingWindow: 1 });
  engine.push(0.5, 0);
  engine.push(0.5, 1000);
  assert.equal(engine.summary().completion, null);
});

test("constructor rejects an inverted valid range", () => {
  assert.throws(() => new HoldDurationEngine({ validMin: 1, validMax: 0.1 }));
});

test("null samples are treated as invalid, not a crash", () => {
  const engine = new HoldDurationEngine({ validMin: 0.1, validMax: 1, smoothingWindow: 1 });
  assert.doesNotThrow(() => engine.push(null, 0));
  assert.equal(engine.state, HOLD_STATE.INVALID);
});

test("reset clears accumulated duration and state", () => {
  const engine = new HoldDurationEngine({
    validMin: 0.1,
    validMax: 1,
    smoothingWindow: 1,
    stabilizationMs: 0,
  });

  engine.push(0.5, 0);
  engine.push(0.5, 3000);
  assert.equal(engine.summary().durationSeconds, 3);

  engine.reset();
  assert.equal(engine.summary().durationSeconds, 0);
  assert.equal(engine.state, HOLD_STATE.INVALID);
});
