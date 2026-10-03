/**
 * Exercise identity: one id, one movement, one configuration.
 *
 * The failure this guards against is a silent one — a card labelled
 * "Standing Side Leg Raise" driving the camera with the knee-raise
 * configuration would still run, still count repetitions, and still look
 * right, while measuring the wrong movement. These tests assert that each
 * of the six prescribed exercises has its own signal, and that the ids
 * used by the demonstration images and the camera engine are the same ids.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { EXERCISE_IMAGES } from "../../movementDemos/exerciseImages.js";
import { EXERCISE_ENGINE_CONFIG, ENGINE_TYPES } from "../config.js";

// Exercise id -> the movement the camera must actually measure. Written
// out here so a change to config.js has to be a deliberate change to this
// expectation too.
const EXPECTED_SIGNALS = {
  "standing-knee-raise": "hipFlexionAngleDeg",
  "standing-side-leg-raise": "hipAbductionAngleDeg",
  "standing-hip-extension": "hipExtensionAngleDeg",
  "seated-marching": "hipFlexionAngleDeg",
  "wall-sit": "kneeFlexionAngleDeg",
};

test("each camera-guided exercise measures the movement it names", () => {
  for (const [id, signal] of Object.entries(EXPECTED_SIGNALS)) {
    const config = EXERCISE_ENGINE_CONFIG[id];

    assert.ok(config, `${id} has no camera configuration`);
    assert.equal(config.signal, signal, `${id} measures the wrong signal`);
  }
});

test("the three standing leg movements are not interchangeable", () => {
  const knee = EXERCISE_ENGINE_CONFIG["standing-knee-raise"];
  const side = EXERCISE_ENGINE_CONFIG["standing-side-leg-raise"];
  const back = EXERCISE_ENGINE_CONFIG["standing-hip-extension"];

  const signals = new Set([knee.signal, side.signal, back.signal]);

  assert.equal(signals.size, 3, "two of these exercises share a signal");
});

test("seated marching shares the hip-flexion signal but not the thresholds", () => {
  // Seated, the thigh starts horizontal, so the same joint angle means
  // something different. Identical thresholds would mean the standing
  // configuration had been copied by mistake.
  const seated = EXERCISE_ENGINE_CONFIG["seated-marching"];
  const standing = EXERCISE_ENGINE_CONFIG["standing-knee-raise"];

  assert.equal(seated.signal, standing.signal);
  assert.notEqual(seated.enterThreshold, standing.enterThreshold);
  assert.notEqual(seated.exitThreshold, standing.exitThreshold);
});

test("wall sit is a hold, not a repetition count", () => {
  const wallSit = EXERCISE_ENGINE_CONFIG["wall-sit"];

  assert.equal(wallSit.engineType, ENGINE_TYPES.HOLD_DURATION);
  assert.ok(wallSit.validMin < wallSit.validMax);
});

test("glute bridge has a diagram but no camera configuration", () => {
  // The library marks it as not measurable from a single camera view, so
  // it must not acquire an engine by accident; it is completed manually.
  assert.ok(EXERCISE_IMAGES["glute-bridge"]);
  assert.equal(EXERCISE_ENGINE_CONFIG["glute-bridge"], undefined);
});

test("every id with a camera configuration is spelled the same everywhere", () => {
  for (const id of Object.keys(EXERCISE_IMAGES)) {
    if (id === "glute-bridge") continue;

    assert.ok(
      Object.prototype.hasOwnProperty.call(EXERCISE_ENGINE_CONFIG, id),
      `${id} has a diagram but no camera configuration under that exact id`,
    );
  }
});

test("no two exercises share a configuration object", () => {
  const seen = new Set();

  for (const [id, config] of Object.entries(EXERCISE_ENGINE_CONFIG)) {
    assert.ok(!seen.has(config), `${id} reuses another exercise's config object`);
    seen.add(config);
  }
});
