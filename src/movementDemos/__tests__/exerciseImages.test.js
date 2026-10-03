/**
 * The exercise-id -> demonstration-image mapping.
 *
 * These tests check the mapping against the files that are actually on
 * disk and against the exercise ids the backend library actually defines,
 * so a renamed file or a mistyped id fails here rather than rendering a
 * broken image in a user's plan.
 */

import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  EXERCISE_IMAGES,
  exerciseImageIds,
  getExerciseImage,
} from "../exerciseImages.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.resolve(here, "../../../public/physio-exercises");

// The six exercises the new diagrams cover.
const EXPECTED_IDS = [
  "standing-knee-raise",
  "standing-side-leg-raise",
  "standing-hip-extension",
  "seated-marching",
  "wall-sit",
  "glute-bridge",
];

test("every expected exercise has a diagram, and no extras are claimed", () => {
  assert.deepEqual(exerciseImageIds().sort(), [...EXPECTED_IDS].sort());
});

test("every mapped file exists in public/physio-exercises", () => {
  for (const id of exerciseImageIds()) {
    const { file } = EXERCISE_IMAGES[id];
    assert.ok(
      existsSync(path.join(publicDir, file)),
      `missing image file for ${id}: ${file}`,
    );
  }
});

test("no image file on disk is left unmapped", () => {
  const onDisk = readdirSync(publicDir).filter((name) => name.endsWith(".png"));
  const mapped = exerciseImageIds().map((id) => EXERCISE_IMAGES[id].file);

  assert.deepEqual(onDisk.sort(), mapped.sort());
});

test("the file name is the exercise id, so the mapping cannot drift from a label", () => {
  for (const id of exerciseImageIds()) {
    assert.equal(EXERCISE_IMAGES[id].file, `${id}.png`);
  }
});

test("each exercise resolves to its own image, never another exercise's", () => {
  const seen = new Set();

  for (const id of exerciseImageIds()) {
    const image = getExerciseImage(id);

    assert.equal(image.src, `/physio-exercises/${id}.png`);
    assert.ok(!seen.has(image.src), `${id} reuses another exercise's image`);
    seen.add(image.src);
  }

  // The specific confusion worth guarding: these three are different
  // movements of the same joint and must not share a diagram.
  assert.notEqual(
    getExerciseImage("standing-side-leg-raise").src,
    getExerciseImage("standing-knee-raise").src,
  );
  assert.notEqual(
    getExerciseImage("standing-hip-extension").src,
    getExerciseImage("standing-knee-raise").src,
  );
});

test("every diagram has alt text describing both panels", () => {
  for (const id of exerciseImageIds()) {
    const { alt } = getExerciseImage(id);

    assert.ok(alt.length > 40, `${id} alt text is too thin to be useful`);
    assert.match(alt, /Left:/);
    assert.match(alt, /Right:/);
  }
});

test("an exercise with no diagram returns null, so the caller can fall back", () => {
  assert.equal(getExerciseImage("chair-sit-to-stand"), null);
  assert.equal(getExerciseImage("not-a-real-exercise"), null);
  assert.equal(getExerciseImage(""), null);
  assert.equal(getExerciseImage(undefined), null);
  assert.equal(getExerciseImage(null), null);
});

test("every mapped id is a real exercise in the backend library", () => {
  // The header above claims this mapping is checked against the ids the
  // backend actually defines; this is that check. An image keyed to an id
  // no plan can ever contain is dead weight that looks like coverage.
  const dataPath = path.resolve(here, "../../../backend/exercise_library/data.py");
  const source = readFileSync(dataPath, "utf8");
  const backendIds = new Set(
    [...source.matchAll(/"exercise_id":\s*"([^"]+)"/g)].map((match) => match[1]),
  );

  assert.ok(backendIds.size > 0, "could not read any exercise ids from the library");

  for (const id of exerciseImageIds()) {
    assert.ok(
      backendIds.has(id),
      `${id} has a diagram but is not an exercise the backend can recommend`,
    );
  }
});
