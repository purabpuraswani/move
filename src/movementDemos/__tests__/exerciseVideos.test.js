/**
 * The movement-id -> instructor-video mapping.
 *
 * The risk worth testing here is not a broken path but a WRONG one: an
 * exercise showing a video of a different movement would look fine and be
 * misleading. These tests check the files exist, that each video is only
 * claimed by movements it actually demonstrates, and that every other
 * exercise resolves to null so the caller falls back instead.
 */

import assert from "node:assert/strict";
import { existsSync, readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  INSTRUCTOR_VIDEOS,
  getExerciseVideo,
  videoMovementIds,
} from "../exerciseVideos.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.resolve(here, "../../../public/assessment-videos");

test("every mapped video file exists on disk", () => {
  for (const entry of INSTRUCTOR_VIDEOS) {
    assert.ok(
      existsSync(path.join(publicDir, entry.file)),
      `missing video file: ${entry.file}`,
    );
  }
});

test("no video on disk is left unmapped", () => {
  const onDisk = readdirSync(publicDir).filter((name) => name.endsWith(".mp4"));
  const mapped = INSTRUCTOR_VIDEOS.map((entry) => entry.file);

  assert.deepEqual(onDisk.sort(), mapped.sort());
});

test("each baseline check resolves to the recording of that movement", () => {
  // Both the test id and the demonstration id reach the same file, because
  // the assessment flow has the latter and the need layer has the former.
  assert.equal(getExerciseVideo("shoulder").src, "/assessment-videos/shoulder-raise.mp4");
  assert.equal(
    getExerciseVideo("assessment-shoulder-raise").src,
    "/assessment-videos/shoulder-raise.mp4",
  );

  assert.equal(getExerciseVideo("ftsst").src, "/assessment-videos/sit-to-stand.mp4");
  assert.equal(
    getExerciseVideo("assessment-chair-sit-to-stand").src,
    "/assessment-videos/sit-to-stand.mp4",
  );

  assert.equal(getExerciseVideo("balance").src, "/assessment-videos/one-leg-stand.mp4");
  assert.equal(
    getExerciseVideo("assessment-one-leg-stand").src,
    "/assessment-videos/one-leg-stand.mp4",
  );
});

test("a library exercise only gets a video of its own movement", () => {
  assert.equal(
    getExerciseVideo("standing-shoulder-raise").src,
    "/assessment-videos/shoulder-raise.mp4",
  );
  assert.equal(
    getExerciseVideo("chair-sit-to-stand").src,
    "/assessment-videos/sit-to-stand.mp4",
  );
  assert.equal(
    getExerciseVideo("supported-single-leg-stand").src,
    "/assessment-videos/one-leg-stand.mp4",
  );
});

test("the six prescribed exercises have no video, and say so", () => {
  // None of these movements is recorded. Returning null is what makes the
  // caller fall back to the animated demonstration and the still diagram,
  // rather than playing a clip of something else.
  const noVideo = [
    "standing-knee-raise",
    "standing-side-leg-raise",
    "standing-hip-extension",
    "seated-marching",
    "wall-sit",
    "glute-bridge",
  ];

  for (const id of noVideo) {
    assert.equal(getExerciseVideo(id), null, `${id} should have no instructor video`);
  }
});

test("an unknown or empty id returns null rather than throwing", () => {
  assert.equal(getExerciseVideo("not-an-exercise"), null);
  assert.equal(getExerciseVideo(""), null);
  assert.equal(getExerciseVideo(undefined), null);
  assert.equal(getExerciseVideo(null), null);
});

test("no two recordings claim the same movement id", () => {
  const ids = videoMovementIds();

  assert.equal(new Set(ids).size, ids.length);
});

test("every recording has a caption describing the movement", () => {
  for (const entry of INSTRUCTOR_VIDEOS) {
    assert.ok(entry.caption.length > 30, `${entry.file} caption is too thin`);
    assert.ok(entry.movements.length >= 1);
  }
});
