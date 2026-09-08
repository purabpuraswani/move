/**
 * Movement Demonstration schema validation.
 * Run with: node --test src/movementDemos/__tests__/
 */

import test from "node:test";
import assert from "node:assert/strict";

import { MovementDemoValidationError, validateMovementDemo } from "../schema.js";
import { getMovementDemo, listMovementDemos, registerMovementDemo } from "../registry.js";

function validDemo(overrides = {}) {
  return {
    movementId: "example-arm-raise",
    title: "Example arm raise",
    category: "exercise",
    durationSeconds: 6,
    phases: [
      { id: "start", label: "Arms at sides", holdSeconds: 2, pose: { armAngleDeg: { left: 0, right: 0 } } },
      { id: "raised", label: "Arms raised", holdSeconds: 2, pose: { armAngleDeg: { left: 90, right: 90 } } },
    ],
    instructions: ["Stand with feet hip width apart.", "Raise both arms out to the side."],
    keyPoints: ["Move only as far as is comfortable."],
    commonMistakes: ["Leaning the trunk to help the arm up."],
    repetitions: 3,
    reference: null,
    ...overrides,
  };
}

test("a well-formed demonstration passes validation", () => {
  assert.doesNotThrow(() => validateMovementDemo(validDemo()));
});

test("a missing required field is rejected", () => {
  const demo = validDemo();
  delete demo.instructions;

  assert.throws(() => validateMovementDemo(demo), MovementDemoValidationError);
});

test("an unknown category is rejected", () => {
  assert.throws(
    () => validateMovementDemo(validDemo({ category: "warmup" })),
    MovementDemoValidationError
  );
});

test("a non-kebab-case movementId is rejected", () => {
  assert.throws(
    () => validateMovementDemo(validDemo({ movementId: "Shoulder Raise" })),
    MovementDemoValidationError
  );
});

test("an empty phases array is rejected", () => {
  assert.throws(
    () => validateMovementDemo(validDemo({ phases: [] })),
    MovementDemoValidationError
  );
});

test("a phase missing holdSeconds is rejected", () => {
  const demo = validDemo();
  delete demo.phases[0].holdSeconds;

  assert.throws(() => validateMovementDemo(demo), MovementDemoValidationError);
});

test("a negative holdSeconds is rejected", () => {
  const demo = validDemo();
  demo.phases[0].holdSeconds = -1;

  assert.throws(() => validateMovementDemo(demo), MovementDemoValidationError);
});

test("instructions must be strings, not arbitrary values", () => {
  assert.throws(
    () => validateMovementDemo(validDemo({ instructions: ["fine", 42] })),
    MovementDemoValidationError
  );
});

test("repetitions may be null for a hold-based movement", () => {
  assert.doesNotThrow(() =>
    validateMovementDemo(validDemo({ repetitions: null }))
  );
});

test("a negative repetitions count is rejected", () => {
  assert.throws(
    () => validateMovementDemo(validDemo({ repetitions: -3 })),
    MovementDemoValidationError
  );
});

test("registerMovementDemo makes a demo retrievable by id", () => {
  registerMovementDemo(validDemo({ movementId: "registry-test-demo" }));

  const found = getMovementDemo("registry-test-demo");

  assert.equal(found.title, "Example arm raise");
  assert.equal(getMovementDemo("does-not-exist"), null);
});

test("registerMovementDemo refuses a duplicate movementId", () => {
  registerMovementDemo(validDemo({ movementId: "registry-duplicate-test" }));

  assert.throws(() =>
    registerMovementDemo(validDemo({ movementId: "registry-duplicate-test" }))
  );
});

test("registerMovementDemo validates before registering", () => {
  assert.throws(() =>
    registerMovementDemo(validDemo({ movementId: "Bad Id" }))
  );
  assert.equal(getMovementDemo("Bad Id"), null);
});

test("listMovementDemos can filter by category", () => {
  registerMovementDemo(validDemo({ movementId: "list-test-assessment", category: "assessment" }));
  registerMovementDemo(validDemo({ movementId: "list-test-exercise", category: "exercise" }));

  const assessments = listMovementDemos("assessment").map((demo) => demo.movementId);

  assert.ok(assessments.includes("list-test-assessment"));
  assert.ok(!assessments.includes("list-test-exercise"));
});
