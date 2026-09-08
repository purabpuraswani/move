/**
 * Movement Demonstration content: the three baseline assessment
 * demonstrations plus the twenty Exercise Library demonstrations (ten from
 * Phase 2, ten added later alongside the second batch of library entries).
 *
 * Importing "../content.js" triggers registration (App.jsx does the same,
 * once, for the real app) — these tests verify what actually got
 * registered, not a hand-copied list.
 */

import test from "node:test";
import assert from "node:assert/strict";

import "../content.js";
import { getMovementDemo, listMovementDemos } from "../registry.js";
import { validateMovementDemo } from "../schema.js";

const ASSESSMENT_IDS = [
  "assessment-shoulder-raise",
  "assessment-chair-sit-to-stand",
  "assessment-one-leg-stand",
];

const EXERCISE_IDS = [
  "exercise-chair-sit-to-stand",
  "exercise-wall-sit",
  "exercise-standing-knee-raise",
  "exercise-supported-calf-raise",
  "exercise-wall-push-up",
  "exercise-standing-side-leg-raise",
  "exercise-standing-hip-extension",
  "exercise-heel-to-toe-stand",
  "exercise-supported-single-leg-stand",
  "exercise-standing-shoulder-raise",
  "exercise-seated-marching",
  "exercise-standing-trunk-rotation",
  "exercise-standing-shoulder-rolls",
  "exercise-standing-ankle-circles",
  "exercise-standing-hamstring-stretch",
  "exercise-glute-bridge",
  "exercise-quadruped-bird-dog",
  "exercise-standing-overhead-reach",
  "exercise-seated-knee-extension",
  "exercise-single-leg-reach-balance",
];

test("exactly three baseline assessment demonstrations are registered", () => {
  const registered = listMovementDemos("assessment").map((d) => d.movementId).sort();
  assert.deepEqual(registered, [...ASSESSMENT_IDS].sort());
});

test("exactly twenty exercise demonstrations are registered", () => {
  const registered = listMovementDemos("exercise").map((d) => d.movementId).sort();
  assert.deepEqual(registered, [...EXERCISE_IDS].sort());
});

for (const id of [...ASSESSMENT_IDS, ...EXERCISE_IDS]) {
  test(`"${id}" is registered and well-formed`, () => {
    const demo = getMovementDemo(id);
    assert.ok(demo, `expected a registered demo for ${id}`);
    assert.doesNotThrow(() => validateMovementDemo(demo));
  });

  test(`"${id}" has at least one phase with non-empty instructions and key points`, () => {
    const demo = getMovementDemo(id);
    assert.ok(demo.phases.length >= 1);
    assert.ok(demo.instructions.length >= 1);
    assert.ok(demo.keyPoints.length >= 1);
    assert.ok(demo.commonMistakes.length >= 1);
  });
}

test("an unregistered id returns null, not a crash", () => {
  assert.equal(getMovementDemo("not-a-real-demo"), null);
});

test("listMovementDemos with no category returns all twenty-three", () => {
  assert.equal(listMovementDemos().length, 23);
});
