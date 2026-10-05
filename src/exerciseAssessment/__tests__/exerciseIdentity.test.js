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
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { EXERCISE_IMAGES } from "../../movementDemos/exerciseImages.js";
import { EXERCISE_ENGINE_CONFIG, ENGINE_TYPES } from "../config.js";

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * What the backend library itself says about each exercise's camera support
 * (`movenet_support.implemented` in backend/exercise_library/data.py). The
 * library is authoritative — this project does not measure a movement the
 * library marks as unmeasurable, and it does measure one the library marks as
 * implemented. Reading it here means the two cannot drift.
 */
function libraryCameraSupport() {
  const source = readFileSync(
    path.resolve(here, "../../../backend/exercise_library/data.py"),
    "utf8",
  );
  const supported = new Map();

  for (const block of source.split(/"exercise_id":\s*"/).slice(1)) {
    const id = block.slice(0, block.indexOf('"'));
    const flags = /_movenet\(\s*supported=\w+,\s*implemented=(\w+)/.exec(block);

    supported.set(id, flags ? flags[1] === "True" : null);
  }

  return supported;
}

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

test("an image never implies a camera configuration the library does not support", () => {
  // An exercise can have a demonstration image without being measurable by a
  // single camera — for the movements this project deliberately does not
  // measure, a reference picture matters MORE, not less, because following the
  // demonstration is the whole instruction. What must never happen is an
  // exercise acquiring an engine for a movement the library marks as
  // unmeasurable, or losing the engine for one it marks as implemented.
  const supported = libraryCameraSupport();

  for (const id of Object.keys(EXERCISE_IMAGES)) {
    const implemented = supported.get(id);
    const hasConfig = Object.prototype.hasOwnProperty.call(EXERCISE_ENGINE_CONFIG, id);

    assert.notEqual(implemented, undefined, `${id} is not an exercise in the library`);

    if (implemented) {
      assert.ok(
        hasConfig,
        `${id} is camera-implemented in the library but has no engine configuration`,
      );
    } else {
      assert.ok(
        !hasConfig,
        `${id} is not camera-measurable, so it must not have an engine configuration`,
      );
    }
  }
});

test("no two exercises share a configuration object", () => {
  const seen = new Set();

  for (const [id, config] of Object.entries(EXERCISE_ENGINE_CONFIG)) {
    assert.ok(!seen.has(config), `${id} reuses another exercise's config object`);
    seen.add(config);
  }
});
