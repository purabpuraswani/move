/**
 * The exercise-id -> demonstration-image mapping.
 *
 * These tests check the mapping against the files that are actually on disk
 * and against the exercise ids the backend library actually defines, so a
 * renamed file or a mistyped id fails here rather than rendering a broken
 * image in a user's plan.
 *
 * There are two kinds of asset, and they are held to different rules because
 * they are different things: diagrams drawn for this project (two panels, one
 * per position) and photographs of real people from the public-domain
 * free-exercise-db. A photograph must not be described as two panels, and a
 * diagram's file name must stay the exercise id.
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

// The exercises the local two-panel diagrams cover.
const DIAGRAM_IDS = [
  "standing-knee-raise",
  "standing-side-leg-raise",
  "standing-hip-extension",
  "seated-marching",
  "wall-sit",
  "glute-bridge",
];

// The exercises a verified free-exercise-db photograph covers. Every one of
// these was looked at and confirmed to show the movement this library
// describes, with the equipment the library's own instructions assume.
const PHOTO_IDS = [
  "standing-shoulder-raise",
  "standing-overhead-reach",
  "standing-trunk-rotation",
  "standing-ankle-circles",
  "seated-knee-extension",
];

test("every expected exercise has an image, and no extras are claimed", () => {
  assert.deepEqual(
    exerciseImageIds().sort(),
    [...DIAGRAM_IDS, ...PHOTO_IDS].sort(),
  );
});

test("every mapped file exists under public/physio-exercises", () => {
  for (const id of exerciseImageIds()) {
    const { file } = EXERCISE_IMAGES[id];
    assert.ok(
      existsSync(path.join(publicDir, file)),
      `missing image file for ${id}: ${file}`,
    );
  }
});

test("no diagram file on disk is left unmapped", () => {
  const onDisk = readdirSync(publicDir).filter((name) => name.endsWith(".png"));
  const mapped = DIAGRAM_IDS.map((id) => EXERCISE_IMAGES[id].file);

  assert.deepEqual(onDisk.sort(), mapped.sort());
});

test("no external photograph on disk is left unmapped", () => {
  const onDisk = readdirSync(path.join(publicDir, "external"))
    .filter((name) => name.endsWith(".jpg"))
    .map((name) => `external/${name}`)
    .sort();
  const mapped = PHOTO_IDS.map((id) => EXERCISE_IMAGES[id].file).sort();

  assert.deepEqual(onDisk, mapped);
});

test("a diagram's file name is the exercise id, so the mapping cannot drift from a label", () => {
  for (const id of DIAGRAM_IDS) {
    assert.equal(EXERCISE_IMAGES[id].file, `${id}.png`);
    assert.equal(EXERCISE_IMAGES[id].kind, "diagram");
  }
});

test("a photograph stays filed under its own exercise id, and its frame is stated", () => {
  for (const id of PHOTO_IDS) {
    const { file, kind } = EXERCISE_IMAGES[id];

    assert.equal(kind, "photo");
    assert.match(
      file,
      new RegExp(`^external/${id}_\\d\\.jpg$`),
      `${id} points at a file that is not its own photograph`,
    );
  }
});

test("each exercise resolves to its own image, never another exercise's", () => {
  const seen = new Set();

  for (const id of exerciseImageIds()) {
    const image = getExerciseImage(id);

    assert.equal(image.src, `/physio-exercises/${EXERCISE_IMAGES[id].file}`);
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

  // And the near-miss pair a name-only match would have merged: an arm raise
  // to shoulder height is not an overhead reach.
  assert.notEqual(
    getExerciseImage("standing-shoulder-raise").src,
    getExerciseImage("standing-overhead-reach").src,
  );
});

test("every image has alt text that describes what is actually shown", () => {
  for (const id of exerciseImageIds()) {
    const { alt } = getExerciseImage(id);

    assert.ok(alt.length > 40, `${id} alt text is too thin to be useful`);

    // A two-panel diagram describes two panels. A photograph must not claim
    // to be one — that is how alt text stops matching its own image.
    if (EXERCISE_IMAGES[id].kind === "diagram") {
      assert.match(alt, /Left:/);
      assert.match(alt, /Right:/);
    } else {
      assert.match(alt, /^Photograph/);
    }
  }
});

test("an exercise with no image returns null, so the caller can fall back", () => {
  // No verified asset exists for a chair sit-to-stand that shows a chair, and
  // a standing squat is a different movement, so there is deliberately no
  // image here rather than a substituted one.
  assert.equal(getExerciseImage("chair-sit-to-stand"), null);
  assert.equal(getExerciseImage("supported-calf-raise"), null);
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
      `${id} has an image but is not an exercise the backend can recommend`,
    );
  }
});
